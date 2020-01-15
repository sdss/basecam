#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-11
# @Filename: camera.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio
import contextlib

import click

from ..events import CameraEvent
from .actor import basecam_parser
from .tools import get_cameras


@basecam_parser.command(name='list')
async def list_(command):
    """Lists cameras connected to the camera system."""

    cameras = [camera.name for camera in command.actor.camera_system.cameras]
    command.done(cameras=cameras, default_cameras=command.actor.default_cameras)


@basecam_parser.command()
@click.argument('CAMERAS', nargs=-1, type=str)
@click.option('-f', '--force', is_flag=True, default=False,
              help='forces a camera to be set as default '
                   'even if it is not connected.')
async def set_default(command, cameras, force):
    """Set default cameras."""

    camera_system = command.actor.camera_system

    camera_names = []
    for camera in cameras:
        for camera_split in camera.split(','):
            if camera_split not in camera_names:
                camera_names.append(camera_split)

    for camera_name in camera_names:
        camera = camera_system.get_camera(name=camera_name)

        if not camera:
            msg = f'camera {camera_name} is not connected.'
            if force:
                command.write('w', text=msg)
            else:
                command.failed(text=f'camera {camera_name} is not connected.')
                return False

    command.actor.set_default_cameras(camera_names)

    command.done(default_cameras=command.actor.default_cameras)


@basecam_parser.command()
@click.argument('CAMERAS', nargs=-1, type=str, required=False)
async def status(command, cameras):
    """Returns the status of a camera."""

    cameras = get_cameras(command)
    if not cameras:
        return

    for camera in cameras:
        status = {'camera': {'name': camera.name,
                             'uid': camera.uid},
                  'status': await camera.get_status(update=True)}
        command.info(status)

    command.done()


@basecam_parser.command()
@click.argument('CAMERAS', nargs=-1, type=str, required=False)
async def reconnect(command, cameras):
    """Reconnects a camera."""

    async def disconnect(camera):
        await camera.shutdown()

    async def connect(camera):
        await camera.connect(force=True)

    cameras = get_cameras(command)
    if not cameras:
        return

    for camera in cameras:

        command.warning(text=f'reconnecting camera {camera.name!r}')

        disconnect_task = asyncio.create_task(disconnect(camera))
        disconnect_result = await command.actor.listener.wait_for(
            CameraEvent.CAMERA_CLOSED, timeout=5)

        if disconnect_result:
            command.info(text=f'camera {camera.name!r} was disconnected.')
        else:
            command.warning(text=f'camera {camera.name!r} failed to disconnect. '
                                 'Will try to reconnect.')
            disconnect_task.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await disconnect_task

        connect_task = asyncio.create_task(connect(camera))
        connect_result = await command.actor.listener.wait_for(
            CameraEvent.CAMERA_OPEN, timeout=5)

        if connect_result:
            command.info(text=f'camera {camera.name!r} was reconnected.')
        else:
            command.warning(text=f'camera {camera.name!r} failed to reconnect.')
            connect_task.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await connect_task

    command.done()
