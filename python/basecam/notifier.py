#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-08-06
# @Filename: notifier.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
#
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-08-06 23:12:12

import enum


class Notifications(enum.Enum):
    """Enumeration of possible notifications."""

    CAMERA_CONNECTED = enum.auto()
    CAMERA_DISCONNECTED = enum.auto()
    CAMERA_OPEN = enum.auto()
    CAMERA_CLOSED = enum.auto()
    EXPOSURE_STARTED = enum.auto()
    EXPOSURE_READING = enum.auto()
    EXPOSURE_FLUSHING = enum.auto()
    EXPOSURE_DONE = enum.auto()
    EXPOSURE_FAILED = enum.auto()


class Notifier(object):
    """