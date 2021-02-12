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
import warnings

from typing import Callable, Optional

import astropy
import astropy.io.fits
import astropy.time
import numpy

import basecam.camera
import basecam.models

from .exceptions import ExposureError, ExposureWarning


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
    """

    def __init__(
        self,
        camera: basecam.camera.BaseCamera,
        filename: Optional[str] = None,
        data: Optional[numpy.ndarray] = None,
        fits_model: Optional[basecam.models.FITSModel] = None,
    ):

        self.camera = camera
        self.data = data
        self.fits_model = fits_model or basecam.models.FITSModel()
        self.filename = filename

        self._obstime: astropy.time.Time = astropy.time.Time.now()

        self.exptime: Optional[float] = None
        self.exptime_n: Optional[float] = None
        self.stack: int = 1
        self.stack_function: Optional[Callable[..., numpy.ndarray]] = None

        self.image_type: Optional[str] = None

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

    def to_hdu(self, context={}) -> astropy.io.fits.HDUList:
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

        fits_model = self.fits_model

        if not fits_model:
            warnings.warn(
                "No FITS model defined. Reverting to default one.", ExposureWarning
            )
            fits_model = basecam.models.FITSModel()

        return fits_model.to_hdu(self, context=context)

    async def write(
        self,
        filename: Optional[str] = None,
        context={},
        overwrite=False,
        checksum=True,
    ) -> astropy.io.fits.HDUList:
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
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        writeto_partial = functools.partial(
            hdulist.writeto, filename, overwrite=overwrite, checksum=checksum
        )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, writeto_partial)

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
    ):

        assert re.match(r".+(\{num.+\}).+", basename), "invalid basename."

        self._basename: str
        self.basename = basename

        self.dirname: pathlib.Path | str = pathlib.Path(dirname)
        self.overwrite: bool = overwrite

        self._last_num = 0
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

    def _eval_dirname(self) -> pathlib.Path:
        """Returns the evaluated dirname."""

        date = astropy.time.Time.now()

        return pathlib.Path(
            eval(f'f"{self.dirname}"', {}, {"date": date, "camera": self.camera})
        )

    def _get_num(self, basename: str) -> int:
        """Returns the counter value."""

        if self.overwrite:
            return self._last_num + 1

        regex = re.compile(re.sub(r"\{num.+\}", "(?P<num>[0-9]*?)", basename))

        dirname = self._eval_dirname()
        all_files = list(map(str, dirname.glob("*")))

        match_files = list(filter(regex.search, all_files))

        if len(match_files) == 0:
            return self._last_num + 1

        values = [int(regex.search(file).group(1)) for file in match_files]
        return max(values) + 1

    def __call__(
        self,
        camera: Optional[basecam.camera.BaseCamera] = None,
    ) -> pathlib.Path:

        camera = camera or self.camera

        if camera:
            expanded_basename = self.basename.format(camera=camera)
        else:
            expanded_basename = self.basename.format()

        num = self._get_num(expanded_basename)
        path = self._eval_dirname() / expanded_basename.format(num=num)
        self._last_num = num

        return path
