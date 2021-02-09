#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-08-05
# @Filename: exceptions.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import inspect

from . import camera


class CameraError(Exception):
    """A custom core exception"""

    def __init__(self, message=""):

        stack = inspect.stack()
        f_locals = stack[1][0].f_locals

        if "self" in f_locals:
            class_ = f_locals["self"]
            if isinstance(class_, camera.BaseCamera):
                camera_name = f_locals["self"].name
            elif isinstance(class_, camera.CameraSystem):
                camera_name = "CAMERA_SYSTEM"
            else:
                camera_name = "UNKNOWN"
            super().__init__(f"{camera_name} - {message}")
        else:
            super().__init__(f"{message}")


class CameraConnectionError(CameraError):
    """An error to be raised if the camera fails to connect/disconnect."""


class ExposureError(Exception):
    """The exposure failed."""


class FITSModelError(Exception):
    """An error related to the FITS model."""


class CardError(FITSModelError):
    """Error raised by a FITS `.Card`."""


class CameraWarning(UserWarning):
    """Base warning."""

    def __init__(self, message, *args, **kwargs):

        stack = inspect.stack()
        f_locals = stack[1][0].f_locals

        if "self" in f_locals:
            class_ = f_locals["self"]
            if isinstance(class_, camera.BaseCamera):
                camera_name = f_locals["self"].name
            elif isinstance(class_, camera.CameraSystem):
                camera_name = "CAMERA_SYSTEM"
            else:
                camera_name = "UNKNOWN"
            super().__init__(f"{camera_name} - {message}")
        else:
            super().__init__(f"{message}")


class ExposureWarning(UserWarning):
    """Warning for exposures."""


class FITSModelWarning(UserWarning):
    """A warnings related to the FITS model."""


class CardWarning(FITSModelWarning):
    """Warning raised by a FITS `.Card`."""
