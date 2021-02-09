#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-03
# @Filename: events.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import enum


__all__ = ["CameraSystemEvent", "CameraEvent"]


class CameraSystemEvent(enum.Enum):
    """Enumeration of camera system events."""

    CAMERA_ADDED = enum.auto()
    CAMERA_REMOVED = enum.auto()


class CameraEvent(enum.Enum):
    """Enumeration of camera events."""

    CAMERA_CONNECTED = "connected"
    CAMERA_CONNECT_FAILED = "connect_failed"
    CAMERA_DISCONNECTED = "disconnected"
    CAMERA_DISCONNECT_FAILED = "disconnect_failed"

    EXPOSURE_FLUSHING = "flushing"
    EXPOSURE_INTEGRATING = "integrating"
    EXPOSURE_READING = "reading"
    EXPOSURE_READ = "read"
    EXPOSURE_FAILED = "failed"
    EXPOSURE_WRITING = "writing"
    EXPOSURE_WRITTEN = "written"

    NEW_SET_POINT = "new_set_point"
    SET_POINT_REACHED = "set_point_reached"
