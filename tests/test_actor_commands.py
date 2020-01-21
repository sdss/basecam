#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-04
# @Filename: test_actor_commands.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio
import os
import types

import astropy.io.fits
import pytest
from asynctest import patch

from basecam import CameraConnectionError, CameraError, ExposureError
from basecam.actor.tools import get_cameras


pytestmark = pytest.mark.asyncio


async def test_ping(actor):

    command = await actor.invoke_mock_command('ping')

    assert command.status.did_succeed
    assert 'Pong' in actor.mock_replies


async def test_help(actor):

    command = await actor.invoke_mock_command('help')

    assert command.status.did_succeed
    assert len(actor.mock_replies) > 2
    assert 'expose' in actor.mock_replies


async def test_list(actor):

    command = await actor.invoke_mock_command('list')

    await asyncio.sleep(1)

    assert command.status.did_succeed
    assert len(actor.mock_replies) == 2
    assert actor.mock_replies[1]['cameras'] == ['test_camera']


@pytest.mark.parametrize('fail_command', (True, False))
@pytest.mark.parametrize('check_cameras', (True, False))
async def test_get_cameras(command, fail_command, check_cameras):

    assert command.actor.default_cameras == ['test_camera']
    assert command.status == command.flags.READY

    assert get_cameras(command,
                       fail_command=fail_command,
                       check_cameras=check_cameras) == command.actor.camera_system.cameras


@pytest.mark.parametrize('fail_command', (True, False))
@pytest.mark.parametrize('check_cameras', (True, False))
async def test_get_cameras_no_default(command, fail_command, check_cameras):

    command.actor.set_default_cameras()
    assert get_cameras(command,
                       fail_command=fail_command,
                       check_cameras=check_cameras) is False


@pytest.mark.parametrize('fail_command', (True, False))
@pytest.mark.parametrize('check_cameras', (True, False))
async def test_get_cameras_no_cameras(command, fail_command, check_cameras):

    command.actor.default_cameras = []
    command.actor.camera_system.cameras = []
    assert get_cameras(command, cameras=[],
                       check_cameras=check_cameras,
                       fail_command=fail_command) is False

    if fail_command:
        assert command.status.did_fail


@pytest.mark.parametrize('fail_command', (True, False))
@pytest.mark.parametrize('check_cameras', (True, False))
async def test_get_cameras_bad_default(command, fail_command, check_cameras):

    command.actor.set_default_cameras('bad_camera')
    assert get_cameras(command,
                       check_cameras=check_cameras,
                       fail_command=fail_command) is False

    if fail_command:
        assert command.status.did_fail


@pytest.mark.parametrize('fail_command', (True, False))
@pytest.mark.parametrize('check_cameras', (True, False))
async def test_get_cameras_pass_cameras(command, fail_command, check_cameras):

    assert get_cameras(command, ['test_camera'],
                       check_cameras=check_cameras,
                       fail_command=fail_command) == command.actor.camera_system.cameras


@pytest.mark.parametrize('fail_command', (True, False))
async def test_get_cameras_check(command, fail_command):

    command.actor.set_default_cameras('test_camera')
    assert command.actor.camera_system.cameras[0].name == 'test_camera'
    command.actor.camera_system.cameras[0].connected = False

    assert get_cameras(command, check_cameras=True,
                       fail_command=fail_command) is False

    if fail_command:
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

    assert command.status.did_succeed
    assert len(actor.mock_replies) == 3  # Running, status reply, and done reply.
    assert actor.mock_replies[1]['status'] == {'temperature': 25., 'cooler': 10.}


async def test_reconnect(actor):

    command = await actor.invoke_mock_command('reconnect')

    assert command.status.did_succeed


async def test_reconnect_disconnect_fails(actor):

    camera = actor.camera_system.cameras[0]

    with patch.object(camera, '_disconnect_internal', side_effect=CameraConnectionError):

        command = await actor.invoke_mock_command('reconnect')

        assert 'failed to disconnect' in actor.mock_replies
        assert command.status.did_succeed


async def test_reconnect_connect_fails(actor):

    camera = actor.camera_system.cameras[0]

    with patch.object(camera, '_connect_internal', side_effect=CameraConnectionError):

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

    assert command.status.did_succeed

    assert 'integrating' in actor.mock_replies
    assert 'reading' in actor.mock_replies

    image_type = image_type or 'object'

    hdu = astropy.io.fits.open(filename)
    assert hdu[0].data is not None
    assert hdu[0].header['IMAGETYP'] == image_type
    assert hdu[0].header['EXPTIME'] == '1.0' if image_type != 'bias' else '0.0'

    if image_type == 'bias':
        assert 'seeting exposure time for bias to 0 seconds.' in actor.mock_replies


async def test_expose_stack(actor):

    command = await actor.invoke_mock_command('expose 1 --stack 2')

    assert command.status.did_succeed

    image_name = actor.mock_replies[-2]['filename']
    assert os.path.exists(image_name)

    hdu = astropy.io.fits.open(image_name)
    assert hdu[0].data is not None
    assert hdu[0].header['EXPTIME'] == '1.0'
    assert hdu[0].header['EXPTIMEN'] == '2.0'
    assert hdu[0].header['STACK'] == '2'


async def test_expose_fails(actor):

    camera = actor.camera_system.cameras[0]

    with patch.object(camera, '_expose_internal', side_effect=ExposureError):

        command = await actor.invoke_mock_command('expose 1')

        assert command.status.did_fail


async def test_expose_filename_fails(actor, tmp_path):

    filename = tmp_path / 'test.fits'

    await actor.camera_system.add_camera(name='AAA', uid='AAA', force=True)
    actor.camera_system.cameras[1].connected = True

    command = await actor.invoke_mock_command(
        f'expose test_camera AAA 1 --filename {filename}')

    assert command.status.did_fail
    assert '-filename can only be used when exposing a single camera' in actor.mock_replies


async def test_shutter_command_exists(actor):

    assert 'shutter' in actor.command_parser.commands


async def test_get_shutter(actor):

    command = await actor.invoke_mock_command('shutter')
    assert command.status.did_succeed
    assert actor.mock_replies[1]['shutter'] is False


@pytest.mark.parametrize('shutter_position', ('open', 'close'))
async def test_set_shutter(actor, shutter_position):

    command = await actor.invoke_mock_command(f'shutter --{shutter_position}')
    assert command.status.did_succeed
    assert actor.camera_system.cameras[0]._shutter_position == (shutter_position == 'open')


async def test_set_shutter_fails(actor):

    camera = actor.camera_system.cameras[0]

    with patch.object(camera, '_set_shutter_internal', side_effect=CameraError):

        command = await actor.invoke_mock_command(f'shutter --open')
        assert command.status.did_fail


async def test_get_temperature(actor):

    temperature = actor.camera_system.cameras[0].temperature

    command = await actor.invoke_mock_command('temperature')

    assert command.status.did_succeed
    assert actor.mock_replies[1]['temperature'] == temperature


async def test_set_temperature(actor):

    command = await actor.invoke_mock_command('temperature 100')
    await command

    assert command.status.did_succeed
    assert actor.camera_system.cameras[0].temperature == 100


async def test_set_temperature_fails(actor):

    camera = actor.camera_system.cameras[0]

    with patch.object(camera, '_set_temperature_internal',
                      side_effect=CameraError('failed to set temperature')):

        command = await actor.invoke_mock_command('temperature 100')

        assert command.status.did_fail
        assert 'failed to set temperature' in actor.mock_replies[1]['error']


async def test_get_binning(actor):

    command = await actor.invoke_mock_command('binning')

    assert command.status.did_succeed

    assert actor.mock_replies[1]['binning'] == [1, 1]


async def test_set_binning(actor):

    command = await actor.invoke_mock_command('binning 2 2')

    assert command.status.did_succeed

    assert actor.mock_replies[1]['binning'] == [2, 2]


async def test_set_binning_fails(actor):

    camera = actor.camera_system.cameras[0]

    with patch.object(camera, '_set_binning_internal',
                      side_effect=CameraError):

        command = await actor.invoke_mock_command('binning 2 2')

        assert command.status.did_fail


async def test_get_area(actor):

    camera = actor.camera_system.cameras[0]

    command = await actor.invoke_mock_command('area')

    assert command.status.did_succeed

    assert actor.mock_replies[1]['area'] == [1, camera.width, 1, camera.height]


async def test_set_area(actor):

    command = await actor.invoke_mock_command('area 10 100 20 40')

    assert command.status.did_succeed

    assert actor.mock_replies[1]['area'] == [10, 100, 20, 40]


async def test_set_area_reset(actor):

    camera = actor.camera_system.cameras[0]

    command = await actor.invoke_mock_command('area 10 100 20 40 --reset')

    assert command.status.did_succeed

    assert actor.mock_replies[1]['area'] == [1, camera.width, 1, camera.height]


async def test_set_area_fails(actor):

    camera = actor.camera_system.cameras[0]

    with patch.object(camera, '_set_image_area_internal',
                      side_effect=CameraError):

        command = await actor.invoke_mock_command('area 10 100 20 40')

        assert command.status.did_fail
