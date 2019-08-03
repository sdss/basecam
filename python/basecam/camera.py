#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-06-19
# @Filename: camera.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
#
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-07-23 12:32:13

import abc

from . import log


class CameraError(Exception):

    def __str__(self):
        return self.__class__.__name__ + ': ' + self.message


class BaseCamera(object, metaclass=abc.ABCMeta):
    """A base class for wrapping a camera API in a standard implementation.

    Parameters
    ----------
    name : str
        The name of the camera.
    autoconnect : bool
        Connect the camera during
    connection_params : dict
        A series of keyword arguments to be passed to the camera to open the
        connection.

    """

    def __init__(self, name, autoconnect=True, **connection_params):

        self.name = name

        self.has_shutter = None
        self._exposure_time = None

        if autoconnect:
            self.connect(**connection_params)

    @abc.abstractmethod
    def connect(self, **conection_params):
        """Connects the camera and performs all the necessary setup."""

        pass

    @abc.abstractmethod
    def _expose_internal(self, exposure_time, shutter=True)
    def expose(self, exposure_time=None):
        """Exposes the camera."""

        pass
