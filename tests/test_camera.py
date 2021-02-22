#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-03
# @Filename: test_camera.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import os
import warnings

import astropy
import astropy.io.fits
import numpy
import pytest

from basecam import (
    CameraConnectionError,
    CameraError,
    CameraWarning,
    Exposure,
    ExposureError,
    ExposureWarning,
)
from basecam.exposure import ImageNamer

from .conftest import EXPOSURE_DIR, CameraSystemTester, VirtualCamera


pytestmark = pytest.mark.asyncio


async def test_camera(camera):
    assert isinstance(camera, VirtualCamera)


async def test_status(camera):

    status = camera.get_status()
    assert status["temperature"] == 25.0

    status_2 = camera.status
    assert status == status_2


async def test_connect_fails(camera, mocker):

    mocker.patch.object(camera, "_connect_internal", side_effect=CameraConnectionError)
    with pytest.raises(CameraConnectionError):
        # Force reconnect.
        await camera.connect(force=True)


async def test_disconnect_fails(camera, mocker):

    mocker.patch.object(
        camera, "_disconnect_internal", side_effect=CameraConnectionError
    )
    with pytest.raises(CameraConnectionError):
        await camera.disconnect()


async def test_expose(camera):

    exposure = await camera.expose(1.0)
    assert isinstance(exposure, Exposure)

    hdu = exposure.to_hdu()

    data = hdu[0].data
    assert data.dtype == numpy.dtype("uint16")
    assert numpy.any(data > 0)

    tai_time = astropy.time.Time("2000-01-01 00:00:00").tai.isot

    header = hdu[0].header
    assert isinstance(header, astropy.io.fits.Header)
    assert header["EXPTIME"] == 1.0
    assert header["IMAGETYP"] == "object"
    assert header["DATE-OBS"] == tai_time
    assert header["CAMNAME"] == camera.name


async def test_expose_negative_exptime(camera):

    with pytest.raises(ExposureError):
        await camera.expose(-0.1)


async def test_expose_bias_positive_exptime(camera):

    with pytest.warns(ExposureWarning):
        await camera.expose(1, image_type="bias")


async def test_expose_write(camera, tmp_path):

    filename = tmp_path / "test.fits"

    await camera.expose(1.0, write=True, filename=filename)

    assert filename.exists()


async def test_expose_bad_data(camera):

    camera.data = None

    with pytest.raises(ExposureError) as ee:
        await camera.expose(0.1)

    assert "data was not taken." in str(ee)


async def test_reconnect_fails(camera):

    with pytest.raises(CameraConnectionError):
        await camera.connect()


async def test_expose_no_filename(camera):

    exposure = await camera.expose(1.0)

    assert exposure.filename is not None

    await exposure.write()
    assert os.path.exists(exposure.filename)
    assert camera.name in str(exposure.filename)


@pytest.mark.parametrize(
    "image_namer",
    (
        ImageNamer(),
        {"basename": "{camera.name}-{num:04d}.fits", "dirname": EXPOSURE_DIR.name},
        None,
    ),
)
async def test_expose_image_namer(camera_system, image_namer):

    camera = VirtualCamera("test_camera", camera_system, image_namer=image_namer)
    await camera.connect()

    exposure = await camera.expose(1.0)

    assert exposure.filename is not None

    await exposure.write()
    assert os.path.exists(exposure.filename)
    assert camera.name in str(exposure.filename)


async def test_bad_image_namer(camera_system):

    with pytest.raises(CameraError):
        VirtualCamera("test_camera", camera_system, image_namer="bad_value")


async def test_expose_stack_two(camera):

    exposure = await camera.expose(1.0, stack=2)

    assert exposure.data.dtype == numpy.dtype("float64")

    hdu = exposure.to_hdu()
    assert hdu[0].header["EXPTIME"] == 1.0
    assert hdu[0].header["EXPTIMEN"] == 2.0
    assert hdu[0].header["STACK"] == 2
    assert hdu[0].header["STACKFUN"] == "median"


async def test_instantiate_no_config():

    camera_system = CameraSystemTester(VirtualCamera)

    assert camera_system._config is None


async def test_instantiate_bad_file():

    with pytest.raises(FileNotFoundError):
        CameraSystemTester(VirtualCamera, camera_config="bad_config")


async def test_camera_error_from_camera_system():
    class TestCameraSystem(CameraSystemTester):
        def raise_camera_error(self):
            raise CameraError("this is a test")

    with pytest.raises(CameraError) as ee:
        camera_system = TestCameraSystem(VirtualCamera)
        camera_system.raise_camera_error()

    assert "CAMERA_SYSTEM" in str(ee)


async def test_camera_error(camera_system):
    class TestCamera(VirtualCamera):
        def raise_camera_error(self):
            raise CameraError("this is a test")

    with pytest.raises(CameraError) as ee:
        camera = TestCamera("FAKE_UID", camera_system)
        camera.raise_camera_error()

    assert "FAKE_UID" in str(ee)
    assert "this is a test" in str(ee)


async def test_camera_error_no_self():

    with pytest.raises(CameraError) as ee:
        raise CameraError("test")

    assert " - " not in str(ee)


async def test_camera_warning(camera_system):
    class TestCamera(VirtualCamera):
        def raise_camera_warning(self):
            warnings.warn("this is a test", CameraWarning)

    with pytest.warns(CameraWarning) as ww:
        camera = TestCamera("FAKE_UID", camera_system)
        camera.raise_camera_warning()

    assert "FAKE_UID" in ww[0].message.args[0]
    assert "this is a test" in ww[0].message.args[0]


async def test_camera_warning_no_self():

    with pytest.warns(CameraWarning) as ww:
        warnings.warn("test", CameraWarning)

    assert " - " not in ww[0].message.args[0]


async def test_camera_warning_camera_system():
    class TestCameraSystem(CameraSystemTester):
        def warns_camera_warning(self):
            warnings.warn("this is a test", CameraWarning)

    with pytest.warns(CameraWarning) as ww:
        camera_system = TestCameraSystem(VirtualCamera)
        camera_system.warns_camera_warning()

    assert "CAMERA_SYSTEM - " in ww[0].message.args[0]


async def test_camera_exception_unknown():
    class Test:
        def warns_camera_warning(self):
            warnings.warn("this is a test", CameraWarning)

    with pytest.warns(CameraWarning) as ww:
        Test().warns_camera_warning()

    assert "UNKNOWN - " in ww[0].message.args[0]


@pytest.mark.parametrize("postprocess", [True, False])
async def test_camera_post_process(postprocess, camera, mocker):
    ppi = mocker.patch.object(camera, "_post_process_internal")
    await camera.expose(0.1, postprocess=postprocess)

    if postprocess:
        ppi.assert_awaited()
    else:
        ppi.assert_not_awaited()


async def test_camera_post_process_fails(camera, mocker):
    mocker.patch.object(camera, "_post_process_internal", side_effect=ExposureError)
    with pytest.raises(ExposureError):
        await camera.expose(0.1, postprocess=True)
