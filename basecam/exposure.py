#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-10
# @Filename: exposure.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import os
import pathlib
import re

import astropy

from .exceptions import ExposureError
from .models import FITSModel


__all__ = ['Exposure', 'ImageNamer']


class Exposure(object):
    """Exposure class. Represents an exposure data and its metadata.

    An `.Exposure` is defined by the raw image taken by the camera, a series
    of attributes that define the exposure (exposure time, shutter, etc.) and
    a data model that is used to generate the FITS file for the exposure.

    Parameters
    ----------
    camera : .BaseCamera
        The instance of a subclass of `.BaseCamera` that took this exposure.
    filename : str
        The filename of the FITS image generated.
    data : numpy.array
        The exposure raw data, as a 2D array.
    fits_model : `.FITSModel`
        The `model <.FITSModel>` to create the FITS image. If `None`, a single
        extension with a basic header will be used.

    Attributes
    ----------
    image_type : str
        The type of image, one of ``bias``, ``flat``, ``dark``, ``object``.
    exptime : float
        The exposure time, in seconds, of a single integration.
    exptime_n : float
        The total exposure time, in seconds. If the image is stacked, this is
        the total time, i.e., the sum of the exposure time of each stacked
        image.
    stack : int
        Number of exposures stacked.
    stack_function : str
        Name of the function used for stacking.
    filename : str
        The path where to write the image.

    """

    def __init__(self, camera, filename=None, data=None, fits_model=None):

        self.camera = camera
        self.data = data
        self.fits_model = fits_model
        self.filename = filename

        self._obstime = None

        self.exptime = None
        self.exptime_n = None
        self.stack = 1
        self.stack_function = None

        self.image_type = None

        self.obstime = astropy.time.Time.now()

    @property
    def obstime(self):
        """The time at the beginning of the observation.

        It must be an `astropy.time.Time` object or a datetime in ISO
        format; in the latter case, UTC scale is assumed.

        """

        return self._obstime

    @obstime.setter
    def obstime(self, value):

        if isinstance(value, astropy.time.Time):
            self._obstime = value
        elif isinstance(value, str):
            self._obstime = astropy.time.Time(value, format='iso', scale='utc')
        else:
            raise ExposureError(f'invalid obstime {value}')

    def to_hdu(self, context={}):
        """Return an `~astropy.io.fits.HDUList` for the image.

        Parameters
        ----------
        context : dict
            A dictionary of arguments used to evaluate the FITS model.

        Returns
        -------
        hdulist : `~astropy.io.fits.HDUList`
            A list of HDUs in which the FITS data model has been evaluated
            for this exposure.

        """

        fits_model = self.fits_model

        if not fits_model:
            fits_model = FITSModel()

        return fits_model.to_hdu(self, context=context)

    def write(self, filename=None, context={}, overwrite=False, checksum=True):
        """Writes the image to disk.

        Parameters
        ----------
        filename : str
            The path where to write the file. If not provided, uses
            ``Exposure.filename``.
        context : dict
            A dictionary of arguments used to evaluate the FITS model.
        overwrite : bool
            Whether to overwrite the image if it exists.
        checksum : bool
            When `True` adds both ``DATASUM`` and ``CHECKSUM`` cards to the
            headers of all HDUs written to the file.

        Returns
        -------
        hdulist : `~astropy.io.fits.HDUList`
            A list of HDUs in which the FITS data model has been evaluated
            for this exposure.

        """

        filename = filename or self.filename
        if not filename:
            raise ExposureError('filename not set.')

        hdulist = self.to_hdu(context=context)

        dirname = os.path.realpath(os.path.dirname(filename))
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        hdulist.writeto(filename, overwrite=overwrite, checksum=checksum)

        return hdulist


class ImageNamer(object):
    """Creates a new sequential filename for an image.

    Parameters
    ----------
    basename : str
        The basename of the image filenames. Must contain a placeholder
        ``num`` in the place where to insert the sequence number. For example,
        ``'test-{num:04d}.fits'`` will produce image names ``test-0001.fits``,
        ``test-0002.fits``, etc. It's also possible to use placeholders for
        camera values, e.g. ``{camera.name}-{num}.fits``.
    dirname : str
        The directory for the images. Can include an expression based on the
        ``date`` substitution which is a `~astropy.time.Time.now` object. For
        example: ``dirname='/data/{int(date.mjd)}'``.
    overwrite : bool
        If `True`, the sequence will start at 1 regardless of the existing
        images. If `False`, the first element in the sequence will be selected
        to avoid colliding with any image already existing in the directory.
    camera : .BaseCamera
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

    def __init__(self, basename='{camera.name}-{num:04d}.fits',
                 dirname='.', overwrite=False, camera=None):

        assert re.match(r'.+(\{num.+\}).+', basename), 'invalid basename.'

        # We want to expand everything except the num first so we "double-escape" it.
        self.basename = re.sub(r'(\{num.+\})', r'{\1}', basename)
        self.dirname = pathlib.Path(dirname)
        self.overwrite = overwrite

        self._last_num = 0
        self.camera = camera

    def _eval_dirname(self):
        """Returns the evaluated dirname."""

        date = astropy.time.Time.now()

        return pathlib.Path(eval(f'f"{self.dirname}"', {}, {'date': date,
                                                            'camera': self.camera}))

    def _get_num(self, basename):
        """Returns the counter value."""

        if self.overwrite:
            return self._last_num + 1

        regex = re.compile(re.sub(r'\{num.+\}', '(?P<num>[0-9]*?)', basename))

        dirname = self._eval_dirname()
        all_files = list(map(str, dirname.glob('*')))

        match_files = list(filter(regex.search, all_files))

        if len(match_files) == 0:
            return self._last_num + 1

        values = [int(regex.search(file).group(1)) for file in match_files]
        return max(values) + 1

    def __call__(self, camera=None):

        camera = camera or self.camera

        if camera:
            expanded_basename = self.basename.format(camera=camera)
        else:
            expanded_basename = self.basename.format()

        num = self._get_num(expanded_basename)
        path = self._eval_dirname() / expanded_basename.format(num=num)
        self._last_num = num

        return path
