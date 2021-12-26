#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2021-02-14
# @Filename: base.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import click

from clu.parsers.click import CluGroup, help_, ping


__all__ = ["camera_parser", "list_"]


@click.group(cls=CluGroup)
def camera_parser():
    pass


camera_parser.add_command(help_)
camera_parser.add_command(ping)


@camera_parser.command(name="list")
@click.option("--available", is_flag=True, help="Lists available cameras.")
async def list_(command, available):
    """Lists cameras connected to the camera system."""

    if available is False:
        cameras = [camera.name for camera in command.actor.camera_system.cameras]
        command.finish(cameras=cameras, default_cameras=command.actor.default_cameras)
    else:
        cameras = command.actor.camera_system.list_available_cameras()
        command.finish(cameras=cameras)
