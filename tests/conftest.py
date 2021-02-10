#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-03
# @Filename: conftest.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio
import glob
import os
import tempfile

import astropy.time
import numpy
import pytest

import clu.testing
from clu.testing import TestCommand
from sdsstools import read_yaml_file

from basecam import BaseCamera, CameraSystem, Exposure
from basecam.actor import CameraActor
from basecam.events import CameraEvent
from basecam.mixins import CoolerMixIn, ExposureTypeMixIn, ImageAreaMixIn, ShutterMixIn
from basecam.notifier import EventListener
from basecam.utils import cancel_task


TEST_CONFIG_FILE = os.path.dirname(__file__) + "/data/test_config.yaml"

EXPOSURE_DIR = tempfile.TemporaryDirectory()


class CameraSystemTester(CameraSystem):

    _connected_cameras = []
    __version__ = "0.1.0"

    def list_available_cameras(self):
        return self._connected_cameras


class VirtualCamera(
    BaseCamera,
    ExposureTypeMixIn,
    ShutterMixIn,
    CoolerMixIn,
    ImageAreaMixIn,
):
    """A virtual camera that does not require hardware.

    This class is mostly intended for testing and development. It behaves
    in all ways as a real camera with pre-defined responses that depend on the
    input parameters.

    """

    # Sets the internal UID for the camera.
    _uid = "DEV_12345"

    def __init__(self, *args, **kwargs):

        self._shutter_position = False

        self.temperature = 25
        self._change_temperature_task = None

        self.width = 640
        self.height = 480

        self._binning = (1, 1)
        self._image_area = (1, 640, 1, 480)

        self.data = False

        super().__init__(*args, **kwargs)

        self.image_namer.dirname = EXPOSURE_DIR.name

    async def _connect_internal(self, **connection_params):

        return True

    def _status_internal(self):
        return {"temperature": self.temperature, "cooler": 10.0}

    async def _get_temperature_internal(self):
        return self.temperature

    async def _set_temperature_internal(self, temperature):
        async def change_temperature():
            await asyncio.sleep(0.2)
            self.temperature = temperature

        await cancel_task(self._change_temperature_task)
        self._change_temperature_task = self.loop.create_task(change_temperature())

    async def _expose_internal(self, exposure, **kwargs):

        image_type = exposure.image_type

        if image_type in ["bias", "dark"]:
            await self.set_shutter(False)
        else:
            await self.set_shutter(True)

        self._notify(CameraEvent.EXPOSURE_FLUSHING)
        self._notify(CameraEvent.EXPOSURE_INTEGRATING)

        # Creates a spiral pattern
        xx = numpy.arange(-5, 5, 0.1)
        yy = numpy.arange(-5, 5, 0.1)
        xg, yg = numpy.meshgrid(xx, yy, sparse=True)
        tile = numpy.sin(xg ** 2 + yg ** 2) / (xg ** 2 + yg ** 2)

        # Repeats the tile to match the size of the image.
        data = numpy.tile(
            tile.astype(numpy.uint16),
            (self.height // len(yy) + 1, self.width // len(yy) + 1),
        )
        data = data[0 : self.height, 0 : self.width]

        # For some tests, we want to set out custom data.
        if self.data is not False:
            data = self.data

        self._notify(CameraEvent.EXPOSURE_READING)

        exposure.data = data
        exposure.obstime = astropy.time.Time("2000-01-01 00:00:00")

        await self.set_shutter(False)

    async def _set_shutter_internal(self, shutter_open):

        self._shutter_position = shutter_open

    async def _get_shutter_internal(self):
        return self._shutter_position

    async def _disconnect_internal(self):

        return True

    async def _get_binning_internal(self):
        return self._binning

    async def _set_binning_internal(self, hbin, vbin):
        self._binning = (hbin, vbin)

    async def _get_image_area_internal(self):

        return self._image_area

    async def _set_image_area_internal(self, area=None):

        if area is None:
            self._image_area = (1, self.width, 1, self.height)
        else:
            self._image_area = area


@pytest.fixture(scope="function", autouse=True)
def clean_exposure_dir():

    for ff in glob.glob(os.path.join(EXPOSURE_DIR.name, "*.fits")):
        os.remove(ff)


@pytest.fixture(scope="module")
def config():
    return read_yaml_file(TEST_CONFIG_FILE)


@pytest.fixture(scope="module")
def event_loop(request):
    """A module-scoped event loop."""

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def camera_system(config, event_loop):

    camera_system = CameraSystemTester(VirtualCamera, camera_config=config).setup()

    yield camera_system

    await camera_system.disconnect()


@pytest.fixture
async def camera(camera_system):

    camera = await camera_system.add_camera("test_camera")
    camera.events = []

    def add_event(event, payload):
        camera.events.append((event, payload))

    listener = EventListener(loop=camera.loop)
    camera.camera_system.notifier.register_listener(listener)
    listener.register_callback(add_event)

    yield camera

    await listener.stop_listening()


@pytest.fixture(scope="module")
async def actor_setup(config):
    """Setups an actor for testing, mocking the client transport.

    This fixture has module scope. Usually you'll want to use it for a
    function-scoped fixture in which you clear the mock replies after each
    test.

    """

    camera_system = CameraSystemTester(VirtualCamera, camera_config=config).setup()

    actor = CameraActor.from_config(config, camera_system)  # type: ignore
    actor = await clu.testing.setup_test_actor(actor)  # type: ignore

    actor._default_cameras = actor.default_cameras  # type: ignore

    yield actor


@pytest.fixture(scope="function")
async def actor(actor_setup):

    await actor_setup.camera_system.add_camera("test_camera")

    yield actor_setup

    # Clear replies in preparation for next test.
    actor_setup.mock_replies.clear()

    for cam in actor_setup.camera_system.cameras:
        actor_setup.camera_system.cameras.remove(cam)

    actor_setup.default_cameras = actor_setup._default_cameras


@pytest.fixture(scope="function")
async def command(actor):

    command = TestCommand(commander_id=1, actor=actor)
    yield command


@pytest.fixture(scope="function")
def exposure(camera):

    exp = Exposure(camera)

    exp.data = numpy.zeros((10, 10), dtype=numpy.uint16)
    exp.obstime = astropy.time.Time.now()
    exp.image_type = "object"

    yield exp
