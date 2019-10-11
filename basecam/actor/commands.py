#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-08-06
# @Filename: commands.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from clu import command_parser as basecam_parser


def get_cameras(command, cameras=None, check_cameras=True):
    """A helper to determine what cameras to use.

    Parameters
    ----------
    command
        The command that wants to access the cameras.
    cameras:
        The output of the ``--cameras`` flag passed to the command.

    Returns
    -------
    cameras : list of `.Camera` instances
        A list of `.Camera` instances that match the input ``cameras`` or,
        if ``cameras=None``, the default cameras. If ``cameras=None`` and
        there are no default cameras defined; or if ``check_cameras=True`` and
        any of the selected cameras is not connected, the command is failed
        and returns `False`.

    """

    default = command.actor.default_cameras

    if cameras is None:
        if default is None or len(default) == 0:
            command.set_status(command.flags.FAILED,
                               text='no default camera set. User the --cameras flag.')
            return False
        else:
            cameras = default

    camera_instances = []
    for camera in cameras:
        camera_instance = command.actor.camera_system.get_camera(name=camera)
        if camera_instance is False:
            command.set_status(command.flags.FAILED,
                               text=f'camera {camera} is not connected.')
            return False
        camera_instances.append(camera_instance)

    if check_cameras:
        for camera_instance in camera_instances:
            if not camera_instance.connected:
                command.set_status(command.flags.FAILED,
                                   text=f'camera {camera_instance.name} '
                                        'has not been initialised.')
                return False

    return camera_instances


@basecam_parser.group()
def camera():
    """Camera-related commands."""
    pass


@camera.command()
async def list(command):
    """Lists cameras connected to the camera system."""

    cameras = [camera.name for camera in command.actor.camera_system.cameras]
    command.done(cameras=cameras)
