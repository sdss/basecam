#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2021-02-14
# @Filename: expose.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
from functools import partial

from typing import TYPE_CHECKING

import click

from clu.parsers.click import unique

from basecam.events import CameraEvent
from basecam.exceptions import ExposureError

from ..tools import get_cameras
from .base import camera_parser


if TYPE_CHECKING:
    from basecam.actor import BasecamCommand

__all__ = ["expose"]


EXPOSURE_STATE = {}


def report_exposure_state(command: BasecamCommand, event, payload):
    global EXPOSURE_STATE

    if event not in CameraEvent:
        return

    name = payload.get("name", "")
    if not name:
        return

    if name not in EXPOSURE_STATE:
        EXPOSURE_STATE[name] = {}

    EXPOSURE_STATE[name].update(payload)

    if event == CameraEvent.EXPOSURE_INTEGRATING:
        state = "integrating"
    elif event == CameraEvent.EXPOSURE_READING:
        state = "reading"
        EXPOSURE_STATE[name].update({"remaining_time": 0.0})
    elif event == CameraEvent.EXPOSURE_DONE:
        state = "done"
        EXPOSURE_STATE[name].update({"remaining_time": 0.0})
    elif event == CameraEvent.EXPOSURE_FAILED:
        state = "failed"
        EXPOSURE_STATE[name].update(
            {
                "remaining_time": 0.0,
                "current_stack": 0,
                "n_stack": 0,
            }
        )
    elif event == CameraEvent.EXPOSURE_IDLE:
        state = "idle"
        EXPOSURE_STATE[name].update(
            {
                "remaining_time": 0.0,
                "current_stack": 0,
                "n_stack": 0,
                "exptime": 0,
                "image_type": "NA",
            }
        )
    elif event == CameraEvent.EXPOSURE_WRITTEN:
        command.info(
            filename={
                "camera": name,
                "filename": payload.get("filename", "UNKNOWN"),
            }
        )
        return
    elif event == CameraEvent.EXPOSURE_POST_PROCESSING:
        command.info(
            state="post_processing",
            image_type=EXPOSURE_STATE[name].get("image_type", "NA"),
        )
        return
    elif event == CameraEvent.EXPOSURE_POST_PROCESS_FAILED:
        command.warning(
            state="post_process_failed",
            image_type=EXPOSURE_STATE[name].get("image_type", "NA"),
            error=payload.get("error", "Error unknown"),
        )
        return
    else:
        return

    command.info(
        exposure_state={
            "camera": name,
            "state": state,
            "image_type": EXPOSURE_STATE[name].get("image_type", "NA"),
            "remaining_time": EXPOSURE_STATE[name].get("remaining_time", 0),
            "exposure_time": EXPOSURE_STATE[name].get("exptime", 0),
            "current_stack": EXPOSURE_STATE[name].get("current_stack", 0),
            "n_stack": EXPOSURE_STATE[name].get("n_stack", 0),
        }
    )


async def expose_one_camera(
    command,
    camera,
    exptime,
    image_type,
    stack,
    filename,
    num,
    no_postprocess,
    **extra_kwargs,
):
    command.info(text=f"exposing camera {camera.name!r}")
    obj = click.get_current_context().obj
    try:
        exposure = await camera.expose(
            exptime,
            image_type=image_type,
            stack=stack,
            filename=filename,
            num=num,
            postprocess=not no_postprocess,
            write=True,
            **extra_kwargs,
        )
        post_process_cb = obj.get("post_process_callback", None)
        if post_process_cb:
            await post_process_cb(command, exposure)
        return True
    except ExposureError as ee:
        command.error(error={"camera": camera.name, "error": str(ee)})
        return False


@camera_parser.command()
@click.argument("CAMERA_NAMES", nargs=-1, type=str, required=False)
@click.argument("EXPTIME", type=float, required=False)
@click.option(
    "--object",
    "image_type",
    flag_value="object",
    default=True,
    show_default=True,
    help="Takes an object exposure.",
)
@click.option(
    "--flat",
    "image_type",
    flag_value="flat",
    show_default=True,
    help="Takes a flat exposure.",
)
@click.option(
    "--dark",
    "image_type",
    flag_value="dark",
    show_default=True,
    help="Takes a dark exposure.",
)
@click.option(
    "--bias",
    "image_type",
    flag_value="bias",
    show_default=True,
    help="Takes a bias exposure.",
)
@click.option(
    "--filename",
    "-f",
    type=str,
    default=None,
    show_default=True,
    help="Filename of the imaga to save.",
)
@click.option(
    "-n",
    "--num",
    type=int,
    default=None,
    help="Sequence number for this exposure filename.",
)
@click.option(
    "--stack",
    "-s",
    type=int,
    default=1,
    show_default=True,
    help="Number of images to stack.",
)
@click.option(
    "-c",
    "--count",
    type=int,
    default=1,
    help="Number of exposures to take.",
)
@click.option(
    "--no-postprocess",
    is_flag=True,
    help="Skip the post-process step, if defined.",
)
@unique()
async def expose(
    command: BasecamCommand,
    camera_names: list[str],
    exptime: float | None = None,
    image_type: str = "object",
    filename: str | None = None,
    num: int | None = None,
    stack: int | None = None,
    count: int = 1,
    no_postprocess: bool = False,
    **exposure_kwargs,
):
    """Exposes and writes an image to disk."""

    for nexp in range(1, count + 1):
        if count > 1:
            command.info(f"Taking exposure {nexp} of {count}")

        cameras = get_cameras(command, cameras=camera_names, fail_command=True)
        if not cameras:  # pragma: no cover
            return

        if image_type == "bias":
            if exptime and exptime > 0:
                command.warning("Setting exposure time for bias to 0 seconds.")
            exptime = 0.0

        if exptime is None:
            return command.fail("Exposure time not provided.")

        if filename and len(cameras) > 1:
            return command.fail("--filename can only be used with a single camera.")

        report_exposure_state_partial = partial(report_exposure_state, command)

        command.actor.listener.register_callback(report_exposure_state_partial)
        jobs = []
        for camera in cameras:
            jobs.append(
                asyncio.create_task(
                    expose_one_camera(
                        command,
                        camera,
                        exptime,
                        image_type,
                        stack,
                        filename,
                        num,
                        no_postprocess,
                        **exposure_kwargs,
                    )
                )
            )

        try:
            results = await asyncio.gather(*jobs)
        except Exception as err:
            command.error(err)
            results = (False,)
        finally:
            # Wait a bit to allow leftover messages sent by the notifier to be output.
            # TODO: this can be improved by checking EXPOSURE_STATE and confirming that
            # all EXPOSURE_WRITTEN has been output for all the cameras (assuming no
            # failures).
            await asyncio.sleep(0.5)

            # Remove the listener.
            command.actor.listener.remove_callback(report_exposure_state_partial)

        if not all(results):
            return command.fail("One or more cameras failed to expose.")
        else:
            for camera in cameras:
                # Reset cameras to idle
                report_exposure_state(
                    command,
                    CameraEvent.EXPOSURE_IDLE,
                    {"name": camera.name},
                )

    return command.finish()
