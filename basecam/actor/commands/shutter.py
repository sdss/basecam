#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2021-02-14
# @Filename: shutter.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import click

from clu.parsers.click import CluCommand

from basecam.exceptions import CameraError

from ..tools import get_cameras


__all__ = ["shutter"]


@click.command(cls=CluCommand)
@click.argument("CAMERAS", nargs=-1, type=str, required=False)
@click.option("--open", "shutter_position", flag_value="open", help="Open the shutter.")
@click.option(
    "--close", "shutter_position", flag_value="close", help="Close the shutter."
)
async def shutter(command, cameras, shutter_position):
    """Controls the camera shutter.

    If called without a shutter position flag, returns the current position
    of the shutter.
    """

    cameras = get_cameras(command, cameras=cameras, fail_command=True)
    if not cameras:  # pragma: no cover
        return

    failed = False
    for camera in cameras:
        if shutter_position is None:
            shutter_now = await camera.get_shutter()
            command.info(
                shutter=dict(
                    camera=camera.name,
                    shutter="open" if shutter_now else "closed",
                )
            )
        else:
            try:
                await camera.set_shutter(shutter_position == "open")
                command.info(
                    shutter=dict(
                        camera=camera.name,
                        shutter="open" if shutter_position else "closed",
                    )
                )
            except CameraError as ee:
                command.error(
                    error=dict(
                        camera=camera.name,
                        error=f"failed commanding shutter: {ee!s}",
                    )
                )
                failed = True

    if failed:
        return command.fail("failed commanding the shutter of one or more cameras.")
    else:
        return command.finish()
