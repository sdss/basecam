#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-03
# @Filename: test_camera_system.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
#
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-10-03 21:53:31

import asyncio

import pytest

from basecam.camera import VirtualCamera
from basecam.exceptions import BasecamNotImplemented, BasecamUserWarning
from basecam.notifier import EventListener

from .conftest import TEST_CONFIG_FILE, TestCameraSystem


pytestmark = pytest.mark.asyncio


async def test_load_config():

    camera_system = TestCameraSystem(VirtualCamera, config=TEST_CONFIG_FILE)

    assert isinstance(camera_system, TestCameraSystem)
    assert 'test_camera' in camera_system.config


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


async def test_get_cameras_not_implemented(camera_system, mocker):

    camera_system.get_connected_cameras = mocker.Mock(side_effect=BasecamNotImplemented)

    await camera_system.start_camera_poller(0.1)
    await asyncio.sleep(0.5)

    assert camera_system._camera_poller is not None
    assert camera_system._camera_poller.running is False


async def test_config_bad_name(camera_system):

    with pytest.warns(BasecamUserWarning):
        data = camera_system.get_camera_config('BAD_CAMERA')

    assert data['name'] == 'BAD_CAMERA'
    assert data['uid'] is None


async def test_no_config(camera_system):

    camera_system.config = None

    with pytest.warns(BasecamUserWarning):
        data = camera_system.get_camera_config('test_camera')

    assert data['name'] == 'test_camera'
    assert data['uid'] is None


async def test_config_from_uid(camera_system):

    data = camera_system.get_camera_config(uid='DEV_12345')

    assert data['name'] == 'test_camera'


async def test_listener(camera_system, event_loop):

    events = []

    async def store_event(event, payload):
        events.append(event)

    listener = EventListener(event_loop)
    listener.register_callback(store_event)

    camera_system.notifier.register_listener(listener)

    await camera_system.add_camera('test_camera')
    await asyncio.sleep(0.1)

    n_events = len(events)
    assert n_events > 0

    # Stop the listener and check that we don't receive more events
    await listener.stop_listener()
    await camera_system.remove_camera('test_camera')
    assert len(events) == n_events

    # Restart

    await listener.start_listener()
    await camera_system.add_camera('test_camera')
    await asyncio.sleep(0.1)

    assert len(events) > n_events
