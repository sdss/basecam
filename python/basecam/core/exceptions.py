# !usr/bin/env python
# -*- coding: utf-8 -*-
#
# Licensed under a 3-clause BSD license.
#
# @Author: Brian Cherinka
# @Date: 2017-12-05 12:01:21
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-07-22 21:33:16


class BasecamError(Exception):
    """A custom core Basecam exception"""

    def __init__(self, message=None):

        message = 'There has been an error' \
            if not message else message

        super(BasecamError, self).__init__(message)


class BasecamNotImplemented(BasecamError):
    """A custom exception for not yet implemented features."""

    def __init__(self, message=None):

        message = 'This feature is not implemented yet.' \
            if not message else message

        super(BasecamNotImplemented, self).__init__(message)


class BasecamAPIError(BasecamError):
    """A custom exception for API errors"""

    def __init__(self, message=None):
        if not message:
            message = 'Error with Http Response from Basecam API'
        else:
            message = 'Http response error from Basecam API. {0}'.format(message)

        super(BasecamAPIError, self).__init__(message)


class BasecamApiAuthError(BasecamAPIError):
    """A custom exception for API authentication errors"""
    pass


class BasecamMissingDependency(BasecamError):
    """A custom exception for missing dependencies."""
    pass


class BasecamWarning(Warning):
    """Base warning for Basecam."""


class BasecamUserWarning(UserWarning, BasecamWarning):
    """The primary warning class."""
    pass


class BasecamSkippedTestWarning(BasecamUserWarning):
    """A warning for when a test is skipped."""
    pass


class BasecamDeprecationWarning(BasecamUserWarning):
    """A warning for deprecated features."""
    pass
