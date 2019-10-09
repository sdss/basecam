#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-08-06
# @Filename: actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from clu.legacy import LegacyActor

from .commands import basecam_parser


class CameraActor(LegacyActor):
    """SDSS-style actor."""

    def __init__(self, camera_system, *args, default_cameras=None, **kwargs):

        self.camera_system = camera_system

        self.default_cameras = default_cameras

        # Pass the camera system instance as the second argument to each parser
        # command (the first argument is always the actor command).
        self.parser_args = [camera_system]

        super().__init__(*args, parser=basecam_parser, **kwargs)
