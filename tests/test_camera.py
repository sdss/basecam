#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-03
# @Filename: test_camera.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import astropy
import astropy.io.fits
import numpy
import pytest

from basecam import Exposure

from .conftest import VirtualCamera


pytestmark = pytest.mark.asyncio


async def test_camera(camera):
    assert isinstance(camera, VirtualCamera)


async def test_status(camera):

    status = await camera.get_status()
    assert status['temperature'] == 25.


async def test_expose(camera):

    exposure = await camera.expose(1.0)
    assert isinstance(exposure, Exposure)

    hdu = exposure.to_hdu()

    data = hdu[0].data
    assert data.dtype == numpy.dtype('uint16')
    assert numpy.any(data > 0)

    tai_time = astropy.time.Time('2000-01-01 00:00:00').tai.isot

    header = hdu[0].header
    assert isinstance(header, astropy.io.fits.Header)
    assert header['EXPTIME'] == '1.0'
    assert header['IMAGETYP'] == 'object'
    assert header['DATE-OBS'] == tai_time
    assert header['CAMNAME'] == camera.name


async def test_shutter(camera):

    assert camera.has_shutter
    assert await camera.get_shutter() is False

    await camera.open_shutter()
    assert await camera.get_shutter() is True

    await camera.close_shutter()
    assert await camera.get_shutter() is False


async def test_bias(camera):

    # Open the shutter
    await camera.open_shutter()

    exposure = await camera.bias()
    hdu = exposure.to_hdu()

    assert hdu[0].header['EXPTIME'] == '0.0'
    assert hdu[0].header['IMAGETYP'] == 'bias'

    calls = camera._set_shutter_internal.mock_calls
    assert len(calls) == 2
    assert calls[1][1][0] is False


async def test_dark(camera):

    exposure = await camera.dark(5)
    hdu = exposure.to_hdu()

    assert hdu[0].header['EXPTIME'] == '5'
    assert hdu[0].header['IMAGETYP'] == 'dark'

    calls = camera._set_shutter_internal.mock_calls
    assert len(calls) == 0


async def test_flat(camera):

    exposure = await camera.flat(5)
    hdu = exposure.to_hdu()

    assert hdu[0].header['EXPTIME'] == '5'
    assert hdu[0].header['IMAGETYP'] == 'flat'

    calls = camera._set_shutter_internal.mock_calls
    assert len(calls) == 2
    assert calls[0][1][0] is True
    assert calls[1][1][0] is False


async def test_object(camera):

    exposure = await camera.object(5)
    hdu = exposure.to_hdu()

    assert hdu[0].header['EXPTIME'] == '5'
    assert hdu[0].header['IMAGETYP'] == 'object'

    calls = camera._set_shutter_internal.mock_calls
    assert len(calls) == 2
    assert calls[0][1][0] is True
    assert calls[1][1][0] is False
