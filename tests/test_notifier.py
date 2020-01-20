#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-06
# @Filename: test_notifier.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio

import asynctest
import pytest

from basecam.events import CameraSystemEvent
from basecam.notifier import EventListener


pytestmark = pytest.mark.asyncio


@pytest.fixture()
async def listener(event_loop):

    listener = EventListener(event_loop)

    yield listener

    await listener.stop_listening()


@pytest.fixture()
async def camera_system(camera_system, listener):

    camera_system.notifier.register_listener(listener)

    camera_system.events = []

    async def record_event(event, __):
        camera_system.events.append(event)

    listener.register_callback(record_event)

    yield camera_system

    for listener in camera_system.notifier.listeners:
        await listener.stop_listening()

    camera_system.events = []
    if record_event in listener.callbacks:
        listener.remove_callback(record_event)
    if listener in camera_system.notifier.listeners:
        camera_system.notifier.remove_listener(listener)


async def test_listener(camera_system, listener):

    events = camera_system.events

    await camera_system.add_camera('test_camera')
    await asyncio.sleep(0.1)

    n_events = len(events)
    assert n_events > 0

    # Stop the listener and check that we don't receive more events
    await listener.stop_listening()
    await camera_system.remove_camera('test_camera')
    assert len(events) == n_events

    # Restart
    await listener.start_listening()
    await camera_system.add_camera('test_camera')
    await asyncio.sleep(0.1)

    assert len(events) > n_events


async def test_callback_function(camera_system, listener):

    func_callback = asynctest.MagicMock()

    listener.register_callback(func_callback)

    await camera_system.add_camera('test_camera')
    await asyncio.sleep(0.1)

    func_callback.assert_called()


async def test_remove_callback(camera_system, listener):

    assert len(listener.callbacks) == 1
    cb = listener.callbacks[0]

    listener.remove_callback(cb)
    assert cb not in listener.callbacks


async def test_remove_bad_callback(listener):

    async def bad_callback(event, payload):
        return

    with pytest.raises(ValueError):
        listener.remove_callback(bad_callback)


async def test_add_same_listener(camera_system, listener):

    camera_system.notifier.register_listener(listener)
    assert len(camera_system.notifier.listeners) == 1


async def test_remove_not_registered_listener(camera_system, event_loop):

    listener_new = EventListener(event_loop)

    with pytest.raises(ValueError):
        camera_system.notifier.remove_listener(listener_new)

    await listener_new.stop_listening()


async def test_filter_notifications(camera_system, listener):

    events = camera_system.events

    # Only notify of cameras being added.
    listener.filter_events = [CameraSystemEvent.CAMERA_ADDED]

    await camera_system.add_camera('test_camera')
    await camera_system.remove_camera('test_camera')

    await asyncio.sleep(0.2)

    assert len(events) == 1


async def test_listener_wait_for(camera_system, listener, event_loop):

    async def add_camera_delayed():
        await asyncio.sleep(0.1)
        await camera_system.add_camera('test_camera')

    task = event_loop.create_task(add_camera_delayed())

    result = await listener.wait_for(CameraSystemEvent.CAMERA_ADDED)
    assert CameraSystemEvent.CAMERA_ADDED in result

    await task


async def test_listener_wait_for_timeout(camera_system, listener, event_loop):

    async def add_camera_delayed():
        await asyncio.sleep(0.2)
        await camera_system.add_camera('test_camera')

    task = event_loop.create_task(add_camera_delayed())

    result = await listener.wait_for(CameraSystemEvent.CAMERA_ADDED, 0.1)
    assert result is False

    await task
