#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-03
# @Filename: tools.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import astropy.io.fits
import astropy.time


__all__ = ['create_fits_image']


def create_fits_image(data, exptime, obstime=None, **extra):
    """Creates a FITS object from an image, with associated header.

    This function is mostly intended to be called by
    `~.Camera._expose_internal` to wrap the exposed image.

    Parameters
    ----------
    data : ~numpy.array
        The array with the image data.
    exptime : float
        The exposure time, in seconds.
    obstime : ~astropy.time.Time
        A `~astropy.time.Time` object with the time of the observation. If
        not provided, uses the current time minus the exposure time.
    extra : ~astropy.io.fits.Header or dict
        A sequence of keyword-value pair to add to the header.

    Returns
    -------
    fits : `~astropy.io.fits.HDUList`
        An HDU list with a single extension containing the image data
        and header.

    """

    if not obstime:
        exptime_delta = astropy.time.TimeDelta(exptime, format='sec')
        obstime = astropy.time.Time.now() - exptime_delta

    header = astropy.io.fits.Header(
        [
            ('DATE-OBS', obstime.isot, 'Date at start of integration'),
            ('TIMESYS', obstime.scale.upper(), 'Time Zone of Date'),
            ('EXPTIME', exptime, 'Exposure time [s]')
        ]
    )

    header.update(extra)

    hdu = astropy.io.fits.PrimaryHDU(data=data, header=header)
    hdul = astropy.io.fits.HDUList([hdu])

    return hdul
