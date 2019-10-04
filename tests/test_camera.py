#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-03
# @Filename: test_camera.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
#
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-10-03 21:09:20

import astropy
import astropy.io.fits
import numpy
import pytest

from basecam.camera import VirtualCamera
from basecam.utils import create_fits_image


pytestmark = pytest.mark.asyncio


async def test_camera(camera):
    assert isinstance(camera, VirtualCamera)


async def test_expose(camera):

    image = await camera.science(1.0)
    assert isinstance(image, astropy.io.fits.HDUList)

    data = image[0].data
    assert data.dtype == numpy.dtype('uint16')
    assert numpy.any(data > 0)

    header = image[0].header
    assert isinstance(header, astropy.io.fits.Header)
    assert header['EXPTIME'] == 1.0
    assert header['DATE-OBS'] == '2000-01-01T00:00:00.000'


async def test_fits_no_obstime():

    data = numpy.zeros((10, 10))

    now = astropy.time.Time.now()

    fits = create_fits_image(data, 1.0)
    image_date = astropy.time.Time(fits[0].header['DATE-OBS'], format='isot')

    assert (image_date - now).sec < 10
