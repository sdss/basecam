#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-04
# @Filename: test_actor_commands.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio

import pytest

from basecam.actor.tools import get_cameras


pytestmark = pytest.mark.asyncio


async def test_list(actor):

    command = await actor.invoke_mock_command('list')

    await asyncio.sleep(1)

    assert command.is_done
    assert len(actor.mock_replies) == 2
    assert actor.mock_replies[1]['cameras'] == ['test_camera']


async def test_get_cameras(command):

    assert command.actor.default_cameras == ['test_camera']
    assert command.status == command.flags.READY

    assert get_cameras(command) == command.actor.camera_system.cameras


async def test_get_cameras_no_default(command):

    command.actor.set_default_cameras()
    assert get_cameras(command) is False


async def test_get_cameras_bad_default(command):

    command.actor.set_default_cameras('bad_camera')
    assert get_cameras(command) is False


async def test_get_cameras_pass_cameras(command):

    assert get_cameras(command, ['test_camera']) == command.actor.camera_system.cameras


async def test_get_cameras_check(command):

    command.actor.set_default_cameras('test_camera')
    assert command.actor.camera_system.cameras[0].name == 'test_camera'
    command.actor.camera_system.cameras[0].connected = False

    assert get_cameras(command, check_cameras=True) is False

    command.actor.camera_system.cameras[0].connected = True


async def test_set_default(actor):

    actor.set_default_cameras()

    await actor.invoke_mock_command('set-default test_camera')
    assert actor.default_cameras == ['test_camera']

    actor.set_default_cameras()

    command_result = await actor.invoke_mock_command('set-default bad_camera')
    assert command_result.did_fail

    command_result = await actor.invoke_mock_command('set-default -f bad_camera')
    assert command_result.is_done
    assert actor.default_cameras == ['bad_camera']

    command_result = await actor.invoke_mock_command('set-default -f sp1 sp2')
    assert command_result.is_done
    assert actor.default_cameras == ['sp1', 'sp2']

    command_result = await actor.invoke_mock_command('set-default -f sp1,sp2 sp3')
    assert command_result.is_done
    assert actor.default_cameras == ['sp1', 'sp2', 'sp3']


async def test_status(actor):

    command = await actor.invoke_mock_command('status')

    assert command.is_done
    assert len(actor.mock_replies) == 3  # Running, status reply, and done reply.
    print(actor.mock_replies[1])
    assert actor.mock_replies[1]['status'] == {'temperature': 25., 'cooler': 10.}
