#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-08-06
# @Filename: commands.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import json
import os

from typing import Any, Dict


__all__ = ["get_cameras", "get_schema"]


def get_cameras(command, cameras=None, check_cameras=True, fail_command=False):
    """A helper to determine what cameras to use.

    Parameters
    ----------
    command
        The command that wants to access the cameras.
    cameras : list
        The list of camera names passed to the command.
    check_cameras : bool
        If any of the cameras is not connected, returns `False`.
    fail_command : bool
        Fails the command before returning `False`.

    Returns
    -------
    cameras : list of `.Camera` instances
        A list of `.Camera` instances that match the input ``cameras`` or,
        if ``cameras=None``, the default cameras. If ``cameras=None`` and
        there are no default cameras defined, returns all the connected
        camera. If ``check_cameras=True`` and any of the selected cameras
        is not connected, the command is failed and returns `False`.

    """

    default = command.actor.default_cameras

    if not cameras:
        if default is None or len(default) == 0:
            camera_instances = command.actor.camera_system.cameras
            cameras = [camera_instance.name for camera_instance in camera_instances]
        else:
            cameras = default

    camera_instances = []
    for camera in cameras:
        camera_instance = command.actor.camera_system.get_camera(name=camera)
        if camera_instance is False:
            if fail_command:
                command.fail(text=f"camera {camera} is not connected.")
            return False
        camera_instances.append(camera_instance)

    if check_cameras:
        for camera_instance in camera_instances:
            if not camera_instance.connected:
                if fail_command:
                    command.fail(
                        text=f"camera {camera_instance.name} "
                        "has not been initialised."
                    )
                return False

    if len(cameras) == 0:
        if fail_command:
            command.fail(text="no cameras connected.")
        return False

    return camera_instances


def get_schema() -> Dict[str, Any]:
    """Returns the actor schema as a dictionary."""

    schema = json.loads(
        open(os.path.join(os.path.dirname(__file__), "schema.json")).read()
    )

    return schema
