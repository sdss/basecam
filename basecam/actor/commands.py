#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-11
# @Filename: camera.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio

import click

from ..exceptions import CameraConnectionError
from .actor import basecam_parser
from .tools import get_cameras


@basecam_parser.command(name='list')
async def list_(command):
    """Lists cameras connected to the camera system."""

    cameras = [camera.name for camera in command.actor.camera_system.cameras]
    command.finish(cameras=cameras, default_cameras=command.actor.default_cameras)


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
                command.fail(text=f'camera {camera_name} is not connected.')
                return False

    command.actor.set_default_cameras(camera_names)

    command.finish(default_cameras=command.actor.default_cameras)


@basecam_parser.command()
@click.argument('CAMERAS', nargs=-1, type=str, required=False)
async def status(command, cameras):
    """Returns the status of a camera."""

    cameras = get_cameras(command, fail_command=True)
    if not cameras:
        return

    for camera in cameras:
        status = {'camera': {'name': camera.name,
                             'uid': camera.uid},
                  'status': await camera.get_status(update=True)}
        command.info(status)

    command.finish()


@basecam_parser.command()
@click.argument('CAMERAS', nargs=-1, type=str, required=False)
@click.option('--timeout', '-t', type=float, default=5., show_default=True,
              help='seconds to wait until disconnect or reconnect command times out.')
async def reconnect(command, cameras, timeout):
    """Reconnects a camera."""

    cameras = get_cameras(command, fail_command=True)
    if not cameras:
        return

    for camera in cameras:

        command.warning(text=f'reconnecting camera {camera.name!r}')

        try:
            await asyncio.wait_for(camera.disconnect(), timeout=timeout)
            command.info(text=f'camera {camera.name!r} was disconnected.')
        except CameraConnectionError as ee:
            command.warning(text=f'camera {camera.name!r} fail to disconnect: {ee} '
                                 'Will try to reconnect.')
        except asyncio.TimeoutError:
            command.warning(text=f'camera {camera.name!r} timed out disconnecting. '
                                 'Will try to reconnect.')

        try:
            await asyncio.wait_for(camera.connect(force=True), timeout=timeout)
            command.finish(text=f'camera {camera.name!r} was reconnected.')
        except CameraConnectionError as ee:
            command.fail(text=f'camera {camera.name!r} fail to reconnect: {ee}')
        except asyncio.TimeoutError:
            command.fail(text=f'camera {camera.name!r} timed out reconnecting.')
