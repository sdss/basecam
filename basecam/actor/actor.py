#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-08-06
# @Filename: actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from clu.legacy import LegacyActor

from clu import command_parser as basecam_parser


class CameraActor(LegacyActor):
    """SDSS-style actor."""

    def __init__(self, camera_system, *args, default_cameras=None, **kwargs):

        self.camera_system = camera_system

        super().__init__(*args, parser=basecam_parser, **kwargs)

        self.default_cameras = None
        self.set_default_cameras(default_cameras)

    def set_default_cameras(self, cameras=None):
        """Sets the camera(s) that will be used by default.

        These cameras will be used by default when a command is issues without
        the ``--cameras`` flag.

        Parameters
        ----------
        cameras : str or list
            A list of camera names or a string with comma-separated camera
            names. If `None`, no cameras will be considered default and
            commands will fail if they do not specify a camera.

        """

        if cameras is None:
            self.default_cameras = None
            return

        if isinstance(cameras, str):
            self.default_cameras = cameras.split(',')
        elif isinstance(cameras, (list, tuple)):
            self.default_cameras = list(cameras)
        else:
            raise ValueError(f'invalid data type for cameras={cameras!r}')

        connected_cameras = [camera.name for camera in self.camera_system.cameras]
        for camera in self.default_cameras:
            if camera not in connected_cameras:
                self.log.warning(f'camera {camera!r} made default but is not connected.')
