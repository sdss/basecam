#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-08-05
# @Filename: exceptions.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
#
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-08-05 12:58:52


class BasecamError(Exception):
    """A custom core Basecam exception"""


class BasecamNotImplemented(BaseException):
    """Not implemented feature."""


class BasecamWarning(Warning):
    """Base warning for Basecam."""


class BasecamUserWarning(UserWarning, BasecamWarning):
    """The primary warning class."""
    pass
