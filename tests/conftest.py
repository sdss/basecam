#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-03
# @Filename: conftest.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio
import os

import astropy.time
import numpy
import pytest
from asynctest import CoroutineMock

import clu.testing
from clu.testing import TestCommand
from sdsstools import read_yaml_file

from basecam.actor import CameraActor
from basecam.camera import BaseCamera, CameraSystem
from basecam.fits import create_fits_image
from basecam.mixins import ExposureTypeMixIn, ShutterMixIn


TEST_CONFIG_FILE = os.path.dirname(__file__) + '/data/test_config.yaml'


class CameraSystemTester(CameraSystem):

    _connected_cameras = []
    _connected = False

    def setup(self):
        self._connected = True
        return self

    def list_available_cameras(self):
        return self._connected_cameras

    async def shutdown(self):
        self._connected = False
        await super().shutdown()


class VirtualCamera(BaseCamera, ExposureTypeMixIn, ShutterMixIn):
    """A virtual camera that does not require hardware.

    This class is mostly intended for testing and development. It behaves
    in all ways as a real camera with pre-defined responses that depend on the
    input parameters.

    """

    # Sets the internal UID for the camera.
    _uid = 'DEV_12345'

    def __init__(self, *args, **kwargs):

        self._shutter_position = False

        self.width = 640
        self.height = 480

        super().__init__(*args, **kwargs)

    async def _connect_internal(self, **connection_params):
        return True

    @property
    def _uid_internal(self):
        return self._uid

    async def _status_internal(self):
        return {'temperature': 25.,
                'cooler': 10.}

    async def _expose_internal(self, exposure_time, image_type='science', **kwargs):

        if image_type in ['bias', 'dark']:
            await self.set_shutter(False)
        else:
            await self.set_shutter(True)

        # Creates a spiral pattern
        xx = numpy.arange(-5, 5, 0.1)
        yy = numpy.arange(-5, 5, 0.1)
        xg, yg = numpy.meshgrid(xx, yy, sparse=True)
        tile = numpy.sin(xg**2 + yg**2) / (xg**2 + yg**2)

        # Repeats the tile to match the size of the image.
        data = numpy.tile(tile.astype(numpy.uint16),
                          (self.height // len(yy) + 1, self.width // len(yy) + 1))
        data = data[0:self.height, 0:self.width]

        obstime = astropy.time.Time('2000-01-01 00:00:00')

        fits_image = create_fits_image(data, exposure_time, obstime=obstime)

        await self.set_shutter(False)

        return fits_image

    async def _set_shutter_internal(self, shutter_open):
        self._shutter_position = shutter_open

    async def _get_shutter_internal(self):
        return self._shutter_position

    async def _disconnect_internal(self):
        pass


@pytest.fixture(scope='module')
def config():
    return read_yaml_file(TEST_CONFIG_FILE)


@pytest.fixture(scope='module')
def event_loop(request):
    """A module-scoped event loop."""

    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='function')
async def camera_system(config, event_loop):

    camera_system = CameraSystemTester(VirtualCamera,
                                       camera_config=config,
                                       loop=event_loop).setup()

    yield camera_system

    await camera_system.shutdown()


@pytest.fixture
async def camera(camera_system):

    camera = await camera_system.add_camera('test_camera')

    # We don't really want to mock _set_shutter_internal, just provide
    # a method to track the calls received.
    camera._set_shutter_internal = CoroutineMock(wraps=camera._set_shutter_internal)

    yield camera


@pytest.fixture(scope='module')
async def actor_setup(config):
    """Setups an actor for testing, mocking the client transport.

    This fixture has module scope. Usually you'll want to use it for a
    function-scoped fixture in which you clear the mock replies after each
    test.

    """

    camera_system = CameraSystemTester(VirtualCamera, camera_config=config).setup()

    actor = CameraActor.from_config(config, camera_system)
    actor = await clu.testing.setup_test_actor(actor)

    await actor.camera_system.add_camera('test_camera')

    yield actor


@pytest.fixture(scope='function')
async def actor(actor_setup):

    # for handler in actor_setup.log.warnings_logger.handlers:
    #     actor_setup.log.warnings_logger.removeHandler(actor_setup.log.warnings_logger)

    yield actor_setup

    # Clear replies in preparation for next test.
    actor_setup.mock_replies.clear()


@pytest.fixture(scope='function')
async def command(actor):

    command = TestCommand(commander_id=1, actor=actor)
    yield command
