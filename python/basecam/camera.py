#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-06-19
# @Filename: camera.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
#
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-09-25 20:20:58

import abc
import asyncio
import logging

from .exceptions import BasecamNotImplemented
from .helpers import LoggerMixIn, Poller
from .utils.configuration import read_yaml_file


class BaseCameraSystem(LoggerMixIn):
    """A base class for the camera system.

    Provides an abstract class for the camera system, including camera
    connection/disconnection event handling, adding and removing cameras, etc.

    While the instance does not handle the loop, it assumes that an event loop
    is running elsewhere, for example via `asyncio.loop.run_forever`.

    Parameters
    ----------
    config : dict or path
        A dictionary with the configuration parameters for the multiple
        cameras that can be present in the system, or the path to a YAML file.
        Refer to the documentation for details on the accepted format.
    loop
        The asyncio event loop.

    """

    _instance = None

    #: The subclass of `.Camera` to use with this class.
    camera_class = None

    def __new__(cls, *args, **kwargs):

        assert cls.camera_class, 'camera_class must be overriden when subclassing.'
        assert isinstance(cls.camera_class, Camera) and cls.camera_class != Camera, \
            'camera_class must be a subclass of Camera.'

        if cls.log_header is None:
            cls.log_header = f'[{cls.__name__.upper()}]: '

        # Implements singleton
        if not cls._instance:
            cls._instance = object.__new__(cls)
        else:
            cls._instance.log('camera system was already instantiated. '
                              'This will reinitialise it.', logging.WARNING)

        return cls._instance

    def __init__(self, config=None, loop=None):

        self.config = config
        self.config_file = None

        self.loop = loop or asyncio.get_event_loop()

        #: list: The list of cameras being handled.
        self.cameras = []

        self._camera_poller = None

        if config and not isinstance(config, dict):
            self.config_file = config
            self.config = read_yaml_file(self.config)
            self.log(f'read configuration file from {self.config_file}')

        # Custom setup for the camera system.
        self._camera_system_internal()

    def _camera_system_internal(self):
        """Setup custom camera system.

        To be overridden by the subclass if needed.

        """

        pass

    def get_camera_config(self, name=None, uid=None):
        """Gets camera parameters from the configuration.

        Parameters
        ----------
        name : str
            The name of the camera.
        uid : str
            The unique identifier of the camera.

        Returns
        -------
        camera_params : `dict`
            A dictionary with the camera parameters.

        """

        assert name or uid, 'either a name or unique identifier are required.'
        assert self.config, 'camera system does not have a configuration.'

        if name:
            assert name in self.config, f'cannot find configuration for {name!r}.'
            config_params = {'name': name}
            config_params.update(self.config[name])
            return config_params

        if uid:
            for name in self.config:
                if self.config[name]['uid'] == uid:
                    config_params = {'name': name}
                    config_params.update(self.config[name])
                    return config_params
            raise ValueError(f'cannot find configuration for UID={uid!r}.')

    async def start_camera_poller(self, interval=1.):
        """Monitors changes in the camera list.

        Issues calls to `.get_connected_cameras` on an interval and compares
        the connected cameras with those in `.cameras`. New found cameras
        are added and cameras not present are cleanly removed.

        This poller should not be initiated if the camera API already provides
        a framework to detect camera events. In that case the event handler
        should be wrapped to call `.on_camera_connected` and
        `.on_camera_disconnected`.

        Similarly, if you prefer to handle camera connections manually, avoid
        starting this poller.

        Parameters
        ----------
        interval : float
            Interval, in seconds, on which the connected cameras are polled
            for changes.

        """

        if self._camera_poller is None:
            self._camera_poller = Poller(self._check_cameras)

        await self._camera_poller.set_delay(interval)

        return self

    async def stop_camera_poller(self):
        """Stops the camera poller if it is running."""

        if self._camera_poller.running:
            await self._camera_poller.stop()

    async def _check_cameras(self):
        """Checks the list of connected cameras.

        This is an internal function to be used only by the camera poller.

        """

        try:
            uids = self.get_connected_cameras()
        except BasecamNotImplemented:
            await self.stop_camera_poller()
            self.log('get_connected cameras is not implemented. '
                     'Stopping camera poller.', logging.ERROR)
            return

        # Checks cameras that are handled but not connected.
        to_remove = []
        for camera in self.cameras:
            if camera.uid not in uids and not camera.force:
                self.log('camera with UID {camera.uid!r} ({camera.name}) '
                         'is not connected.', logging.INFO)
                to_remove.append(camera.name)

        for camera_name in to_remove:
            self.remove_camera(camera_name)

        # Checks cameras that are connected but not yet being handled.
        camera_uids = [camera.uid for camera in self.cameras]
        for uid in uids:
            if uid not in camera_uids:
                self.log('detected new camera with UID {uid!r}.', logging.INFO)
                await self.add_camera(uid=uid, use_config=True)

    def get_connected_cameras(self):
        """Lists the connected cameras as reported by the camera system.

        This method should not be confused with `.cameras`, which lists the
        `.Camera` instance currently being handled by the `.CameraSystem`.
        `.get_connected_cameras` returns the cameras that the camera API
        believes are connected at any given time. While both lists are likely
        to match if the camera poller or camera event handling is used, it does
        not need to be the case if cameras are being handled manually.

        Returns
        -------
        connected_cameras : `list`
            A list of unique identifiers of the connected cameras. The unique
            identifiers must match those in the configuration file.

        """

        raise BasecamNotImplemented

    async def add_camera(self, name=None, uid=None, use_config=True,
                         force=False, **kwargs):
        """Adds a new `.Camera` instance to `.cameras`.

        If ``use_config=True``, the camera connection parameter will be
        queried from the configuration using the provided ``name`` or ``uid``.

        Parameters
        ----------
        name : str
            The name of the camera.
        uid : str
            The unique identifier for the camera.
        use_config : bool
            Whether to read the information from the configuration.
        force : bool
            Forces the camera to stay in the `.CameraSystem` list even if it
            does not appear in the system camera list.
        kwargs
            Other arguments to be passed to `.Camera` during initialisation.
            If ``use_config=True``, these parameters override the default
            configuration where applicable.

        Returns
        -------
        camera : `.Camera`
            The new `.Camera` instance.

        """

        assert name or uid, 'either name or uid are required.'

        if use_config and self.config:
            camera_params = self.get_camera_config(name=name, uid=uid)
        else:
            camera_params = {'name': name or uid, 'uid': uid}

        camera_params.update(kwargs)

        name = camera_params['name']
        if name in [camera.name for camera in self.cameras]:
            self.log('a camera {name!r} is already connected.', logging.WARNING)
            return

        self.log(f'adding camera with parameters {camera_params!r}')

        camera_params['camera_system'] = self
        camera_params['force'] = force

        camera = self.camera_class(**camera_params)

        # If the autoconnect parameter is set, connects the camera.
        connection_params = camera_params.get('connection_params', None)
        if not connection_params or \
                (connection_params and connection_params.get('autoconnect', True)):
            await camera.connect()

        self.cameras.append(camera)

        if self.actor:
            self.actor.on_camera_connected(camera)

        return camera

    async def remove_camera(self, name=None, uid=None):
        """Removes a camera, cancelling any ongoing process.

        Parameters
        ----------
        name : str
            The name of the camera.
        uid : str
            The unique identifier for the camera.

        """

        for camera in self.cameras:
            if camera.name == name or camera.uid == uid:

                await camera.shutdown()
                self.cameras.remove(camera)

                self.log(f'removed camera {name!r}.')

                if self.actor:
                    self.actor.on_camera_disconnected(camera)

                return

        raise ValueError(f'camera {name} is not connected.')

    def on_camera_connected(self, uid):
        """Event handler for a newly connected camera.

        Parameters
        ----------
        uid : str
            The unique identifier for the camera.

        """

        return asyncio.run_coroutine_threadsafe(self.add_camera(uid=uid), self.loop).result()

    def on_camera_disconnected(self, uid):
        """Event handler for a camera that was disconnected.

        Parameters
        ----------
        uid : str
            The unique identifier for the camera.

        """

        return asyncio.run_coroutine_threadsafe(self.remove_camera(uid=uid), self.loop).result()


class BaseCamera(object, metaclass=abc.ABCMeta):
    """A base class for wrapping a camera API in a standard implementation.

    Instantiating the `.Camera` class does not open the camera and makes it
    ready to be used. To do that, call and await `.connect`.

    Parameters
    ----------
    name : str
        The name of the camera.
    camera_system : `.CameraSystem` instance
        The camera system handling this camera.
    force : bool
        Forces the camera to stay in the `.CameraSystem` list even if it
        does not appear in the system camera list.
    connection_params : dict
        A series of parameters to be passed to the camera to open
        the connection. The format of the parameters must follow the structure
        of the configuration file.
    kwargs : dict
        Other parameters used to define the camera geometry, defaults, etc.
        The format of the parameters must follow the structure of the
        configuration file.

    """

    def __init__(self, name, camera_system, force=False, connection_params=None,
                 **kwargs):

        self.name = name

        self.camera_system = camera_system
        self.actor = self.camera_system.actor

        self.force = force

        self.connection_params = connection_params or {}

    async def connect(self, **connection_params):
        """Connects the camera and performs all the necessary setup.

        Parameters
        ----------
        connection_params : dict
            A series of keyword arguments to be passed to the camera to open
            the connection.

        """

        self.connection_params.update(connection_params or {})

        await self._connect_internal(**connection_params)

        return self

    @abc.abstractmethod
    async def _connect_internal(self):
        pass

    @abc.abstractproperty
    def uid(self):
        """Get the unique identifier for the camera (e.g., serial number)."""

        pass

    async def expose(self, exposure_time=None):
        """Exposes the camera."""

        await self._expose_internal()

    @abc.abstractmethod
    async def _expose_internal(self, exposure_time, shutter=True):
        pass

    async def shutdown(self):
        pass
