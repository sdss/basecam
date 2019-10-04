#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-03
# @Filename: test_camera.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
#
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-10-03 20:05:56

import astropy.io.fits
import numpy
import pytest

from basecam.camera import VirtualCamera


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
