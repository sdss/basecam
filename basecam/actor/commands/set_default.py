#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2021-02-14
# @Filename: set_default.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import click

from .base import camera_parser


__all__ = ["set_default"]


@camera_parser.command()
@click.argument("CAMERAS", nargs=-1, type=str)
@click.option(
    "-f",
    "--force",
    is_flag=True,
    default=False,
    help="Forces a camera to be set as default even if it is not connected.",
)
async def set_default(command, cameras, force):
    """Set default cameras."""

    camera_system = command.actor.camera_system

    camera_names = []
    for camera in cameras:
        for camera_split in camera.split(","):
            if camera_split not in camera_names:
                camera_names.append(camera_split)

    for camera_name in camera_names:
        camera = camera_system.get_camera(name=camera_name)

        if not camera:
            msg = f"camera {camera_name} is not connected."
            if force:
                command.write("w", text=msg)
            else:
                return command.fail(
                    camera=camera.name, text=f"camera {camera_name} is not connected."
                )

    command.actor.set_default_cameras(camera_names)

    command.finish(default_cameras=command.actor.default_cameras)
