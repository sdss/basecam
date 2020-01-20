#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-04
# @Filename: test_actor_commands.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio
import types

import astropy.io.fits
import pytest

from basecam.actor.tools import get_cameras


pytestmark = pytest.mark.asyncio


async def test_ping(actor):

    command = await actor.invoke_mock_command('ping')

    assert command.status == command.status.DONE
    assert 'Pong' in actor.mock_replies


async def test_help(actor):

    command = await actor.invoke_mock_command('help')

    assert command.status == command.status.DONE
    assert len(actor.mock_replies) > 2
    assert 'expose' in actor.mock_replies


async def test_list(actor):

    command = await actor.invoke_mock_command('list')

    await asyncio.sleep(1)

    assert command.status == command.status.DONE
    assert len(actor.mock_replies) == 2
    assert actor.mock_replies[1]['cameras'] == ['test_camera']


async def test_get_cameras(command):

    assert command.actor.default_cameras == ['test_camera']
    assert command.status == command.flags.READY

    assert get_cameras(command) == command.actor.camera_system.cameras


async def test_get_cameras_no_default(command):

    command.actor.set_default_cameras()
    assert get_cameras(command, fail_command=True) is False


async def test_get_cameras_no_cameras(command):

    command.actor.default_cameras = []
    command.actor.camera_system.cameras = []
    assert get_cameras(command, cameras=[], fail_command=True) is False
    assert command.status.did_fail


async def test_get_cameras_bad_default(command):

    command.actor.set_default_cameras('bad_camera')
    assert get_cameras(command, fail_command=True) is False
    assert command.status.did_fail


async def test_get_cameras_pass_cameras(command):

    assert get_cameras(command, ['test_camera']) == command.actor.camera_system.cameras


async def test_get_cameras_check(command):

    command.actor.set_default_cameras('test_camera')
    assert command.actor.camera_system.cameras[0].name == 'test_camera'
    command.actor.camera_system.cameras[0].connected = False

    assert get_cameras(command, check_cameras=True, fail_command=True) is False
    assert command.status.did_fail

    command.actor.camera_system.cameras[0].connected = True


async def test_set_default(actor):

    actor.set_default_cameras()

    await actor.invoke_mock_command('set-default test_camera')
    assert actor.default_cameras == ['test_camera']

    actor.set_default_cameras()

    command_result = await actor.invoke_mock_command('set-default bad_camera')
    assert command_result.status.did_fail

    command_result = await actor.invoke_mock_command('set-default -f bad_camera')
    assert command_result.status == command_result.status.DONE
    assert actor.default_cameras == ['bad_camera']

    command_result = await actor.invoke_mock_command('set-default -f sp1 sp2')
    assert command_result.status == command_result.status.DONE
    assert actor.default_cameras == ['sp1', 'sp2']

    command_result = await actor.invoke_mock_command('set-default -f sp1,sp2 sp3')
    assert command_result.status == command_result.status.DONE
    assert actor.default_cameras == ['sp1', 'sp2', 'sp3']


async def test_status(actor):

    command = await actor.invoke_mock_command('status')

    assert command.status == command.status.DONE
    assert len(actor.mock_replies) == 3  # Running, status reply, and done reply.
    assert actor.mock_replies[1]['status'] == {'temperature': 25., 'cooler': 10.}


async def test_reconnect(actor):

    command = await actor.invoke_mock_command('reconnect')

    assert command.status == command.status.DONE


async def test_reconnect_disconnect_fails(actor):

    actor.camera_system.cameras[0].raise_on_disconnect = True
    command = await actor.invoke_mock_command('reconnect')

    assert 'failed to disconnect' in actor.mock_replies
    assert command.status == command.status.DONE


async def test_reconnect_connect_fails(actor):

    actor.camera_system.cameras[0].raise_on_connect = True
    command = await actor.invoke_mock_command('reconnect')

    assert 'failed to connect' in actor.mock_replies
    assert command.status.did_fail


async def test_reconnect_timesout(actor):

    async def _sleeper(self, *args, **kwargs):
        await asyncio.sleep(1)
        return True

    camera = actor.camera_system.cameras[0]
    camera._disconnect_internal = types.MethodType(_sleeper, camera)
    camera._connect_internal = types.MethodType(_sleeper, camera)

    command = await actor.invoke_mock_command('reconnect --timeout 0.05')

    assert command.status.did_fail
    assert 'timed out' in actor.mock_replies


@pytest.mark.parametrize('image_type', (None, 'object', 'flat', 'bias', 'dark'))
async def test_expose(actor, tmp_path, image_type):

    filename = tmp_path / 'test_exposure.fits'

    command_str = f'expose 1 --filename {filename}'
    if image_type:
        command_str += f' --{image_type}'

    command = await actor.invoke_mock_command(command_str)

    assert command.status == command.status.DONE

    assert 'integrating' in actor.mock_replies
    assert 'reading' in actor.mock_replies

    image_type = image_type or 'object'

    hdu = astropy.io.fits.open(filename)
    assert hdu[0].data is not None
    assert hdu[0].header['IMAGETYP'] == image_type
    assert hdu[0].header['EXPTIME'] == '1.0' if image_type != 'bias' else '0.0'

    if image_type == 'bias':
        assert 'seeting exposure time for bias to 0 seconds.' in actor.mock_replies


async def test_expose_fails(actor):

    actor.camera_system.cameras[0].raise_on_expose = True

    command = await actor.invoke_mock_command('expose 1')

    assert command.status == command.status.FAILED


async def test_expose_filename_fails(actor, tmp_path):

    filename = tmp_path / 'test.fits'

    await actor.camera_system.add_camera(name='AAA', uid='AAA', force=True)
    actor.camera_system.cameras[1].connected = True

    command = await actor.invoke_mock_command(
        f'expose test_camera AAA 1 --filename {filename}')

    assert command.status == command.status.FAILED
    assert '-filename can only be used when exposing a single camera' in actor.mock_replies
