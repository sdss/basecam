#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-08-05
# @Filename: exceptions.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import inspect


class CameraError(Exception):
    """A custom core exception"""

    def __init__(self, message=''):

        stack = inspect.stack()
        camera_name = stack[1][0].f_locals['self'].name

        super().__init__(f'Camera {camera_name} - {message}')


class CameraConnectionError(CameraError):
    """An error to be raised if the camera fails to connect/disconnect."""


class ExposureError(CameraError):
    """The exposure failed."""


class CameraWarning(UserWarning):
    """Base warning."""
