#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-20
# @Filename: test_mixins.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio

import pytest

from basecam.events import CameraEvent


pytestmark = pytest.mark.asyncio


async def test_bias(camera, mocker):

    mock = mocker.patch.object(
        camera,
        "_set_shutter_internal",
        wraps=camera._set_shutter_internal,
    )

    # Open the shutter
    await camera.open_shutter()

    exposure = await camera.bias()
    hdu = exposure.to_hdu()

    assert hdu[0].header["EXPTIME"] == 0.0
    assert hdu[0].header["IMAGETYP"] == "bias"

    calls = mock.mock_calls
    assert len(calls) == 2
    assert calls[1][1][0] is False


async def test_dark(camera, mocker):

    mock = mocker.patch.object(
        camera,
        "_set_shutter_internal",
        wraps=camera._set_shutter_internal,
    )

    exposure = await camera.dark(5)
    hdu = exposure.to_hdu()

    assert hdu[0].header["EXPTIME"] == 5
    assert hdu[0].header["IMAGETYP"] == "dark"

    calls = mock.mock_calls
    assert len(calls) == 0


async def test_flat(camera, mocker):

    mock = mocker.patch.object(
        camera,
        "_set_shutter_internal",
        wraps=camera._set_shutter_internal,
    )

    exposure = await camera.flat(5)
    hdu = exposure.to_hdu()

    assert hdu[0].header["EXPTIME"] == 5
    assert hdu[0].header["IMAGETYP"] == "flat"

    calls = mock.mock_calls
    assert len(calls) == 2
    assert calls[0][1][0] is True
    assert calls[1][1][0] is False


async def test_object(camera, mocker):

    mock = mocker.patch.object(
        camera,
        "_set_shutter_internal",
        wraps=camera._set_shutter_internal,
    )

    exposure = await camera.object(5)
    hdu = exposure.to_hdu()

    assert hdu[0].header["EXPTIME"] == 5
    assert hdu[0].header["IMAGETYP"] == "object"

    calls = mock.mock_calls
    assert len(calls) == 2
    assert calls[0][1][0] is True
    assert calls[1][1][0] is False


async def test_shutter(camera):

    assert await camera.get_shutter() is False

    await camera.open_shutter()
    assert await camera.get_shutter() is True

    await camera.close_shutter()
    assert await camera.get_shutter() is False


async def test_get_temperature(camera):

    assert await camera.get_temperature() == camera.temperature


async def test_set_temperature(camera):

    await camera.set_temperature(100.0)

    assert await camera.get_temperature() == 100.0

    assert CameraEvent.NEW_SET_POINT in camera.events[0]
    assert camera.events[0][1]["temperature"] == 100.0
    assert CameraEvent.SET_POINT_REACHED in camera.events[1]


async def test_set_temperature_override(camera):

    await camera.set_temperature(100.0)

    await asyncio.sleep(0.01)
    await camera.set_temperature(0.0)

    assert await camera.get_temperature() == 0.0
    assert CameraEvent.SET_POINT_REACHED in camera.events[-1]


async def test_get_binning(camera):

    assert await camera.get_binning() == (1, 1)


async def test_set_binning(camera):

    await camera.set_binning(2, 2)
    assert await camera.get_binning() == (2, 2)


async def test_set_binning_only_hbin(camera):

    await camera.set_binning(2)
    assert await camera.get_binning() == (2, 2)


async def test_get_image_area(camera):

    assert await camera.get_image_area() == (1, camera.width, 1, camera.height)


async def test_set_image_area(camera):

    await camera.set_image_area((10, 100, 20, 40))
    assert await camera.get_image_area() == (10, 100, 20, 40)

    await camera.set_image_area()
    assert await camera.get_image_area() == (1, camera.width, 1, camera.height)
