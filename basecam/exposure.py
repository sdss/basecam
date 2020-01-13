#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-10
# @Filename: exposure.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import astropy

from .exceptions import ExposureError
from .model import Extension, FITSModel


__all__ = ['Exposure']


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
        The exposure time, in seconds.
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

        hdulist.writeto(filename, overwrite=overwrite, checksum=checksum)

        return hdulist
