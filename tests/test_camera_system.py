#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-03
# @Filename: test_camera_system.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
#
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-10-05 22:10:37

import asyncio
import logging

import pytest

from basecam.camera import VirtualCamera
from basecam.exceptions import CameraWarning
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

    camera_system.get_connected_cameras = mocker.Mock(side_effect=NotImplementedError)

    await camera_system.start_camera_poller(0.1)
    await asyncio.sleep(0.5)

    assert camera_system._camera_poller is not None
    assert camera_system._camera_poller.running is False


async def test_config_bad_name(camera_system):

    with pytest.warns(CameraWarning):
        data = camera_system.get_camera_config('BAD_CAMERA')

    assert data['name'] == 'BAD_CAMERA'
    assert data['uid'] is None


async def test_config_bad_uid(camera_system):

    with pytest.warns(CameraWarning):
        data = camera_system.get_camera_config(uid='BAD_UID')

    assert data['name'] == 'BAD_UID'
    assert data['uid'] == 'BAD_UID'


async def test_no_config(camera_system):

    camera_system.config = None

    with pytest.warns(CameraWarning):
        data = camera_system.get_camera_config('test_camera')

    assert data['name'] == 'test_camera'
    assert data['uid'] is None


async def test_config_from_uid(camera_system):

    data = camera_system.get_camera_config(uid='DEV_12345')

    assert data['name'] == 'test_camera'
    assert data['uid'] == 'DEV_12345'
    assert data['shutter'] is True


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


@pytest.mark.parametrize('param,value', [('name', 'test_camera'),
                                         ('uid', 'DEV_12345')])
async def test_add_camerera_already_connected(camera_system, caplog, param, value):

    camera = await eval(f'camera_system.add_camera({param}={value!r})')
    assert camera
    assert getattr(camera, param) == value

    caplog.clear()

    new_camera = await camera_system.add_camera(name='test_camera')

    assert len(caplog.record_tuples) > 0

    last_record = caplog.record_tuples[-1]
    assert last_record[1] == logging.WARNING
    assert 'already connected' in last_record[2]

    assert new_camera == camera


async def test_remove_camera_not_connected(camera_system):

    with pytest.raises(ValueError):
        await camera_system.remove_camera('not_connected_camera')


@pytest.mark.parametrize('params', ['name="test_camera"', 'uid="DEV_12345"',
                                    'name="test_camera", uid="DEV_12345"'])
async def test_get_camera(camera_system, params):

    await camera_system.add_camera(name='test_camera')

    camera = eval(f'camera_system.get_camera({params})')

    assert camera.name == 'test_camera'
    assert camera.uid == 'DEV_12345'


async def test_get_camera_not_found(camera_system):

    camera = camera_system.get_camera('bad_camera')

    assert camera is False


async def test_get_camera_no_params(camera_system):

    await camera_system.add_camera(name='test_camera')
    camera = camera_system.get_camera()

    assert camera


async def test_expose(camera_system):

    await camera_system.add_camera(name='test_camera')

    exposure = await camera_system.science('test_camera', 5)

    header = exposure[0].header
    assert header['CAMNAME'] == 'TEST_CAMERA'
    assert header['EXPTIME'] == 5
    assert header['IMAGETYP'] == 'OBJECT'
