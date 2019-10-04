#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-03
# @Filename: test_camera_system.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
#
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-10-03 18:22:50

import asyncio

import pytest

from basecam.camera import VirtualCamera


pytestmark = pytest.mark.asyncio


async def test_system(camera_system):
    assert camera_system._connected is True


async def test_discover(camera_system):

    await camera_system.start_camera_poller(0.1)
    camera_system._connected_cameras = ['DEV_12345']

    await asyncio.sleep(0.2)

    assert len(camera_system.cameras) == 1
    assert isinstance(camera_system.cameras[0], VirtualCamera)

    camera_system._connected_cameras = []

    await asyncio.sleep(0.2)

    assert len(camera_system.cameras) == 0


async def test_camera_connected(camera_system):

    camera_system.on_camera_connected('DEV_12345')

    await asyncio.sleep(0.1)

    assert len(camera_system.cameras) == 1
    assert isinstance(camera_system.cameras[0], VirtualCamera)

    camera_system.on_camera_disconnected('DEV_12345')

    await asyncio.sleep(0.1)

    assert len(camera_system.cameras) == 0
