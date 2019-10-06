#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-08-05
# @Filename: exceptions.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
#
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-10-05 21:55:45


class CameraError(Exception):
    """A custom core exception"""


class ExposureError(CameraError):
    """The exposure failed."""


class CameraWarning(UserWarning):
    """Base warning."""
