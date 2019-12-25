#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-03
# @Filename: conftest.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio
import os

import pytest
from asynctest import CoroutineMock

import clu.testing
from basecam.actor import CameraActor
from basecam.camera import CameraSystem, VirtualCamera
from basecam.utils import read_yaml_file
from clu.testing import TestCommand


TEST_CONFIG_FILE = os.path.dirname(__file__) + '/data/test_config.yaml'


class CameraSystemTester(CameraSystem):

    _connected_cameras = []
    _connected = False

    def setup(self):
        self._connected = True
        return self

    def get_connected_cameras(self):
        return self._connected_cameras

    async def shutdown(self):
        self._connected = False
        await super().shutdown()


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
                                       config=config,
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

    camera_system = CameraSystemTester(VirtualCamera, config=config).setup()

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
