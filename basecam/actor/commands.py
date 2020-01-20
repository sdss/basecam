#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-11
# @Filename: camera.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio

import click

from ..events import CameraEvent
from ..exceptions import CameraConnectionError, ExposureError
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
              help='Forces a camera to be set as default '
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
    if not cameras:  # pragma: no cover
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
              help='Seconds to wait until disconnect or reconnect command times out.')
async def reconnect(command, cameras, timeout):
    """Reconnects a camera."""

    cameras = get_cameras(command, fail_command=True)
    if not cameras:  # pragma: no cover
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


@basecam_parser.command()
@click.argument('CAMERAS', nargs=-1, type=str, required=False)
@click.argument('EXPTIME', type=float, required=False)
@click.option('--object', 'image_type', flag_value='object', default=True,
              show_default=True, help='Takes an object exposure.')
@click.option('--flat', 'image_type', flag_value='flat',
              show_default=True, help='Takes a flat exposure.')
@click.option('--dark', 'image_type', flag_value='dark',
              show_default=True, help='Takes a dark exposure.')
@click.option('--bias', 'image_type', flag_value='bias',
              show_default=True, help='Takes a bias exposure.')
@click.option('--filename', '-f', type=str, default=None,
              show_default=True, help='Filename of the imaga to save.')
async def expose(command, cameras, exptime, image_type, filename):
    """Exposes and writes an image to disk."""

    async def stage(event, payload):
        name = payload.get('name', None)
        if event == CameraEvent.EXPOSURE_FLUSHING:
            stage = 'flushing'
        elif event == CameraEvent.EXPOSURE_INTEGRATING:
            stage = 'integrating'
        elif event == CameraEvent.EXPOSURE_READING:
            stage = 'reading'
        elif event == CameraEvent.EXPOSURE_FAILED:
            stage = 'failed'
        else:
            return
        command.info(name=name, stage=stage)

    cameras = get_cameras(command, cameras=cameras, fail_command=True)
    if not cameras:  # pragma: no cover
        return

    if image_type == 'bias':
        if exptime and exptime > 0:
            command.warning('seeting exposure time for bias to 0 seconds.')
        exptime = 0.0

    if filename and len(cameras) > 1:
        return command.fail('--filename can only be used when exposing '
                            'a single camera.')

    for camera in cameras:

        command.actor.listener.register_callback(stage)
        command.info(text=f'exposing camera {camera.name!r}')

        try:
            # Schedule camera.expose as a task to allow the events to be
            # notified concurrently.
            exposure = await command.actor.loop.create_task(
                camera.expose(exptime, image_type=image_type, filename=filename))
            exposure.write()
        except ExposureError as ee:
            return command.fail(text='error found while exposing camera '
                                     f'{camera.name!r}: {ee!s}')
        finally:
            command.actor.listener.remove_callback(stage)

    return command.finish()
