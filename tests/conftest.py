#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-03
# @Filename: conftest.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
#
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-10-03 19:57:16

# import asyncio
import os

import pytest

from basecam.camera import CameraSystem, VirtualCamera
from basecam.utils import read_yaml_file


class TestCameraSystem(CameraSystem):

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
    return read_yaml_file(os.path.dirname(__file__) + '/data/cameras.yaml')


# @pytest.yield_fixture(scope='module')
# def event_loop(request):
#     """A module scoped event loop."""
#     loop = asyncio.get_event_loop_policy().new_event_loop()
#     yield loop
#     loop.close()


@pytest.fixture(scope='function')
async def camera_system(config, event_loop):

    camera_system = TestCameraSystem(VirtualCamera, config=config, loop=event_loop).setup()
    yield camera_system
    await camera_system.shutdown()


@pytest.fixture
async def camera(camera_system):

    camera = await camera_system.add_camera('DEV_12345')
    yield camera
