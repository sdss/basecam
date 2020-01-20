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

from basecam import (CameraConnectionError, CameraWarning,
                     Exposure, ExposureError, ExposureWarning)

from .conftest import VirtualCamera


pytestmark = pytest.mark.asyncio


async def test_camera(camera):
    assert isinstance(camera, VirtualCamera)


async def test_status(camera):

    status = await camera.get_status()
    assert status['temperature'] == 25.


async def test_connect_fails(camera):

    camera.raise_on_connect = True

    with pytest.raises(CameraConnectionError):
        # Force reconnect.
        await camera.connect(force=True)


async def test_disconnect_fails(camera):

    camera.raise_on_disconnect = True

    with pytest.raises(CameraConnectionError):
        await camera.disconnect()


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


async def test_expose_negative_exptime(camera):

    with pytest.raises(ExposureError):
        await camera.expose(-0.1)


async def test_expose_bias_positive_exptime(camera):

    with pytest.warns(ExposureWarning):
        await camera.expose(1, image_type='bias')


async def test_expose_write(camera, tmp_path):

    filename = tmp_path / 'test.fits'

    await camera.expose(1.0, write=True, filename=filename)

    assert filename.exists()


async def test_expose_bad_data(camera):

    camera.data = None

    with pytest.raises(ExposureError) as ee:
        await camera.expose(0.1)

    assert 'data was not taken.' in str(ee)


async def test_reconnect_fails(camera):

    with pytest.raises(CameraConnectionError):
        await camera.connect()


async def test_connect_uid_warning(camera):

    camera._uid = None
    camera.camera_config['uid'] = None

    with pytest.warns(CameraWarning):
        await camera.connect(force=True)
