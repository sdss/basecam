#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2021-02-14
# @Filename: test_actor_legacy.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import pytest

import clu.testing
from clu.legacy import LegacyActor

from basecam.actor import BaseCameraActor

from .conftest import CameraSystemTester, VirtualCamera


class ActorLegacyTest(BaseCameraActor, LegacyActor):
    pass


@pytest.fixture()
async def actor_setup(config):
    """Setups an actor for testing, mocking the client transport.

    This fixture has module scope. Usually you'll want to use it for a
    function-scoped fixture in which you clear the mock replies after each
    test.
    """
    camera_system = CameraSystemTester(VirtualCamera, camera_config=config).setup()

    actor = ActorLegacyTest.from_config(config, camera_system)  # type: ignore
    actor = await clu.testing.setup_test_actor(actor)  # type: ignore

    actor._default_cameras = actor.default_cameras  # type: ignore

    yield actor


@pytest.fixture()
async def actor(actor_setup):
    await actor_setup.camera_system.add_camera("test_camera")

    yield actor_setup

    # Clear replies in preparation for next test.
    actor_setup.mock_replies.clear()

    for cam in actor_setup.camera_system.cameras:
        actor_setup.camera_system.cameras.remove(cam)

    actor_setup.default_cameras = actor_setup._default_cameras


async def test_get_area(actor):
    camera = actor.camera_system.cameras[0]
    command = await actor.invoke_mock_command("area")
    assert command.status.did_succeed
    reply = f"test_camera,1,{camera.width},1,{camera.height}"
    assert actor.mock_replies[1]["area"] == reply


async def test_set_area(actor):
    command = await actor.invoke_mock_command("area 10 100 20 40")
    assert command.status.did_succeed
    assert actor.mock_replies[1]["area"] == "test_camera,10,100,20,40"


async def test_get_temperature(actor):
    temperature = actor.camera_system.cameras[0].temperature
    command = await actor.invoke_mock_command("temperature")
    assert command.status.did_succeed
    assert actor.mock_replies[1]["temperature"] == f"test_camera,{temperature}"
