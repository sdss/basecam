#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-03
# @Filename: events.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import enum


__all__ = ['CameraSystemEvent', 'CameraEvent']


class CameraSystemEvent(enum.Enum):
    """Enumeration of camera system events."""

    CAMERA_ADDED = enum.auto()
    CAMERA_REMOVED = enum.auto()


class CameraEvent(enum.Enum):
    """Enumeration of camera events."""

    CAMERA_OPEN = enum.auto()
    CAMERA_CLOSED = enum.auto()
    EXPOSURE_STARTED = enum.auto()
    EXPOSURE_FLUSHING = enum.auto()
    EXPOSURE_EXPOSING = enum.auto()
    EXPOSURE_READING = enum.auto()
    EXPOSURE_DONE = enum.auto()
    EXPOSURE_FAILED = enum.auto()
