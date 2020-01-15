#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-11
# @Filename: camera.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import click

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
    """Prints the status of a camera."""

    if len(cameras) == 0:
        cameras = get_cameras(command)
        if not cameras:
            return
