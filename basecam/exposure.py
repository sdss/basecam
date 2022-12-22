#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-10
# @Filename: exposure.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import functools
import os
import pathlib
import re
import shutil
import tempfile
import warnings

from typing import Callable, List, Optional, Tuple, Union

import astropy
import astropy.io.fits as fits
import astropy.time
import astropy.wcs
import numpy
from astropy.io.fits import BinTableHDU, HDUList, ImageHDU

from sdsstools.time import get_sjd

import basecam.camera
import basecam.models
from basecam.exceptions import ExposureError

from .utils import gzip_async


__all__ = ["Exposure", "ImageNamer"]


class Exposure(object):
    """Exposure class. Represents an exposure data and its metadata.

    An `.Exposure` is defined by the raw image taken by the camera, a series
    of attributes that define the exposure (exposure time, shutter, etc.) and
    a data model that is used to generate the FITS file for the exposure.

    Parameters
    ----------
    camera
        The instance of a subclass of `.BaseCamera` that took this exposure.
    filename
        The filename of the FITS image generated.
    data
        The exposure raw data, as a 2D array.
    fits_model
        The `model <.FITSModel>` to create the FITS image. If `None`, a single
        extension with a basic header will be used.
    wcs
        The WCS object describing the astrometry of this exposure.

    Attributes
    ----------
    image_type
        The type of image, one of ``bias``, ``flat``, ``dark``, ``object``.
    exptime : float
        The exposure time, in seconds, of a single integration.
    exptime_n : float
        The total exposure time, in seconds. If the image is stacked, this is
        the total time, i.e., the sum of the exposure time of each stacked
        image.
    stack : int
        Number of exposures stacked.
    stack_function
        Name of the function used for stacking.
    filename
        The path where to write the image.
    wcs : ~astropy.wcs.WCS
        The WCS object describing the astrometry of this exposure.
    """

    def __init__(
        self,
        camera: basecam.camera.BaseCamera,
        filename: Optional[str] = None,
        data: Optional[numpy.ndarray] = None,
        fits_model: Optional[basecam.models.FITSModel] = None,
        wcs: Optional[astropy.wcs.WCS] = None,
    ):

        self.camera = camera
        self.data = data
        self.fits_model = fits_model.copy() if fits_model else None
        self.filename = filename

        self._obstime: astropy.time.Time = astropy.time.Time.now()

        self.exptime: Optional[float] = None
        self.exptime_n: Optional[float] = None
        self.stack: int = 1
        self.stack_function: Optional[Callable[..., numpy.ndarray]] = None
        self.image_type: Optional[str] = None

        self._extra_hdus: List[Tuple[Union[BinTableHDU, ImageHDU], Optional[int]]] = []

        self.wcs = wcs

    @property
    def obstime(self) -> astropy.time.Time:
        """The time at the beginning of the observation.

        It must be an `astropy.time.Time` object or a datetime in ISO
        format; in the latter case, UTC scale is assumed.
        """

        return self._obstime

    @obstime.setter
    def obstime(self, value: astropy.time.Time):

        if isinstance(value, astropy.time.Time):
            self._obstime = value
        elif isinstance(value, str):
            self._obstime = astropy.time.Time(value, format="iso", scale="utc")
        else:
            raise ExposureError(f"invalid obstime {value}")

    def add_hdu(self, hdu: Union[BinTableHDU, ImageHDU], index: Optional[int] = None):
        """Adds an HDU to the list of extensions.

        Parameters
        ----------
        hdu
            The `~astropy.io.fits.BinTableHDU` or `~astropy.io.fits.ImageHDU` HDU to
            append.
        index
            The index where the extension will be added. Extra HDUs are inserted in
            order after the FITS model has been generated. ``index=None`` appends the
            new HDU at the end of the list. Note that ``astropy.io.fits`` may change
            the final order of the extensions to ensure that a primary HDU remains
            as the first HDU.
        """

        assert isinstance(hdu, (BinTableHDU, ImageHDU)), "invalid HDU type"

        self._extra_hdus.append((hdu, index))

    def to_hdu(self, context={}) -> HDUList:
        """Return an `~astropy.io.fits.HDUList` for the image.

        Parameters
        ----------
        context
            A dictionary of arguments used to evaluate the FITS model.

        Returns
        -------
        hdulist
            A list of HDUs in which the FITS data model has been evaluated
            for this exposure.
        """

        fits_model = self.fits_model or basecam.models.FITSModel()

        hdulist = fits_model.to_hdu(self, context=context)
        for hdu, index in self._extra_hdus:
            if index:
                hdulist.insert(index, hdu)
            else:
                hdulist.append(hdu)

        return hdulist

    async def write(
        self,
        filename: Optional[str] = None,
        context={},
        overwrite=False,
        checksum=True,
        retry=True,
    ) -> HDUList:
        """Writes the image to disk.

        Parameters
        ----------
        filename
            The path where to write the file. If not provided, uses
            ``Exposure.filename``.
        context
            A dictionary of arguments used to evaluate the FITS model.
        overwrite
            Whether to overwrite the image if it exists.
        checksum
            When `True` adds both ``DATASUM`` and ``CHECKSUM`` cards to the
            headers of all HDUs written to the file.
        retry
            If `True` and the image fails to write, tries again. This can be
            useful when writing to network volumen where failures are more
            frequent.

        Returns
        -------
        hdulist
            A list of HDUs in which the FITS data model has been evaluated
            for this exposure.
        """

        filename = filename or self.filename
        if not filename:
            raise ExposureError("filename not set.")

        hdulist = self.to_hdu(context=context)

        dirname = os.path.realpath(os.path.dirname(filename))
        os.makedirs(dirname, exist_ok=True)

        loop = asyncio.get_event_loop()

        filename = str(filename)

        for ntry in range(2):
            try:
                if filename.endswith(".gz"):

                    # We compress in a local temporary file, which is faster when we are
                    # going to save a file across the network.
                    tmp_name = tempfile.NamedTemporaryFile(suffix=".gz").name

                    # Astropy compresses with gzip -9 which takes forever.
                    # Instead we compress manually with -1, which is still pretty good.
                    writeto_partial = functools.partial(
                        hdulist.writeto,
                        tmp_name[:-3],
                        overwrite=overwrite,
                        checksum=checksum,
                    )
                    await loop.run_in_executor(None, writeto_partial)
                    await gzip_async(tmp_name[:-3], complevel=1)

                    shutil.move(tmp_name, filename)

                else:

                    writeto_partial = functools.partial(
                        hdulist.writeto,
                        filename,
                        overwrite=overwrite,
                        checksum=checksum,
                    )

                    await loop.run_in_executor(None, writeto_partial)

                break

            except Exception as err:
                if ntry == 0 and retry is True:
                    warnings.warn(
                        f"Retrying after exposure writing failed with error: {err}"
                    )
                    continue
                else:
                    raise ExposureError(f"Failed writing exposure to disk: {err}")

        # Horrible hack to try to fix compressed headers.
        update_hdu = fits.open(filename, mode="update")
        for ext in update_hdu:
            try:
                BSCALE = ext.header.pop("BSCALE", 1)
                BZERO = ext.header.pop("BZERO", 2**15)
                ext.header["BSCALE"] = BSCALE
                ext.header["BZERO"] = BZERO
            except Exception:
                pass
        update_hdu.close()

        return hdulist


class ImageNamer(object):
    """Creates a new sequential filename for an image.

    Parameters
    ----------
    basename
        The basename of the image filenames. Must contain a placeholder
        ``num`` in the place where to insert the sequence number. For example,
        ``'test-{num:04d}.fits'`` will produce image names ``test-0001.fits``,
        ``test-0002.fits``, etc. It's also possible to use placeholders for
        camera values, e.g. ``{camera.name}-{num}.fits``.
    dirname
        The directory for the images. Can include an expression based on the
        ``date`` substitution which is a `~astropy.time.Time.now` object. For
        example: ``dirname='/data/{camera.uid}/{int(date.mjd)}'``.
    overwrite
        If `True`, the sequence will start at 1 regardless of the existing
        images. If `False`, the first element in the sequence will be selected
        to avoid colliding with any image already existing in the directory.
    camera
        A `.BaseCamera` instance. It can also be passed when calling the
        instance.
    reset_sequence
        Resets the sequence number when the directory changes (for example when
        the MJD rolls over).

    Examples
    --------
    >>> namer = ImageNamer('{camera.name}-{num:04d}.fits', dirname='testdir')
    >>> namer(camera=camera)
    PosixPath('testdir/my_camera-0001.fits')
    >>> namer(camera=camera)
    PosixPath('testdir/my_camera-0002.fits')
    """

    def __init__(
        self,
        basename: str = "{camera.name}-{num:04d}.fits",
        dirname: str = ".",
        overwrite: bool = False,
        camera: Optional[basecam.camera.BaseCamera] = None,
        reset_sequence: bool = True,
    ):

        assert re.match(r".+(\{num.+\}).+", basename), "invalid basename."

        self._basename: str
        self.basename = basename

        self.dirname: Union[pathlib.Path, str] = pathlib.Path(dirname)
        self.overwrite: bool = overwrite

        self._last_num: int = 0

        self._previous_dirname: str | None = None
        self._reset_sequence = reset_sequence

        self.camera = camera

    @property
    def basename(self) -> str:
        """The image name pattern."""
        return self._basename

    @basename.setter
    def basename(self, value: str):
        """Sets the basename."""
        # We want to expand everything except the num first so we "double-escape" it.
        self._basename = re.sub(r"(\{num.+\})", r"{\1}", value)

    def get_dirname(self) -> pathlib.Path:
        """Returns the evaluated dirname."""

        date = astropy.time.Time.now()
        sjd = get_sjd(raise_error=False)

        dirname = pathlib.Path(
            eval(
                f'f"{self.dirname}"',
                {},
                {"date": date, "camera": self.camera, "sjd": sjd},
            )
        )

        if self._previous_dirname and self._previous_dirname != str(dirname):
            if self._reset_sequence:
                self._last_num = 0

        self._previous_dirname = str(dirname)

        return dirname

    def _get_num(self, basename: str) -> int:
        """Returns the counter value."""

        if self.overwrite:
            return self._last_num + 1

        regex = re.compile(re.sub(r"\{num.+\}", "(?P<num>[0-9]*?)", basename))

        dirname = self.get_dirname()
        all_files = list(map(str, dirname.glob("*")))

        match_files = list(filter(regex.search, all_files))

        if len(match_files) == 0:
            return self._last_num + 1

        matches = [regex.search(file) for file in match_files]
        values = [int(match.group(1)) for match in matches if match is not None]
        return max(values) + 1

    def __call__(
        self,
        camera: Optional[basecam.camera.BaseCamera] = None,
        update_num: bool = True,
        num: Optional[int] = None,
    ) -> pathlib.Path:

        camera = camera or self.camera

        if camera:
            expanded_basename = self.basename.format(camera=camera)
        else:
            expanded_basename = self.basename.format()

        dirname = self.get_dirname()
        num = num or self._get_num(expanded_basename)
        path = dirname / expanded_basename.format(num=num)

        if update_num:
            self._last_num = num

        return path
