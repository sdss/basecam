#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-06-19
# @Filename: camera.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import abc
import asyncio
import logging
import os
import warnings

import numpy

from sdsstools import read_yaml_file

from .events import CameraEvent, CameraSystemEvent
from .exceptions import (CameraConnectionError, CameraError,
                         CameraWarning, ExposureError, ExposureWarning)
from .exposure import Exposure, ImageNamer
from .models import basic_fits_model
from .notifier import EventNotifier
from .utils import LoggerMixIn, Poller


__all__ = ['CameraSystem', 'BaseCamera']


class CameraSystem(LoggerMixIn, metaclass=abc.ABCMeta):
    """A base class for the camera system.

    Provides an abstract class for the camera system, including camera
    connection/disconnection event handling, adding and removing cameras, etc.

    While the instance does not handle the loop, it assumes that an event loop
    is running elsewhere, for example via `asyncio.loop.run_forever`.

    Parameters
    ----------
    camera_class : `.BaseCamera` subclass
        The subclass of `.BaseCamera` to use with this camera system.
    camera_config : dict or path
        A dictionary with the configuration parameters for the multiple
        cameras that can be present in the system, or the path to a YAML file.
        Refer to the documentation for details on the accepted format.
    logger_name : str
        The name of the logger to use. If not specified, the name of the class
        will be used.
    log_header : str
        A string to be prefixed to each message logged.
    loop
        The asyncio event loop.

    """

    def __init__(self, camera_class, camera_config=None, logger_name=None,
                 log_header=None, loop=None):

        assert issubclass(camera_class, BaseCamera) and camera_class != BaseCamera, \
            'camera_class must be a subclass of BaseCamera.'

        self.camera_class = camera_class

        logger_name = logger_name or self.__class__.__name__.upper()
        log_header = log_header or f'[{logger_name.upper()}]: '

        LoggerMixIn.__init__(self, logger_name, log_header=log_header)

        self.camera_config = camera_config
        self.camera_config_file = None

        self.loop = loop or asyncio.get_event_loop()
        self.loop.set_exception_handler(self.logger.asyncio_exception_handler)

        #: list: The list of cameras being handled.
        self.cameras = []

        self._camera_poller = None

        #: .EventNotifier: Notifies of `.CameraSystemEvent` and `.CameraEvent` events.
        self.notifier = EventNotifier()

        if camera_config is None:
            self.camera_config = camera_config
        elif camera_config and not isinstance(camera_config, dict):
            self.camera_config_file = os.path.expandvars(os.path.expanduser(str(camera_config)))
            if not os.path.exists(self.camera_config_file):
                warnings.warn(f'cannot open configuration file {self.camera_config_file}',
                              CameraWarning)
            else:
                self.camera_config = read_yaml_file(self.camera_config_file)
                self.log(f'read configuration file from {self.camera_config_file}')
        else:
            self.camera_config = self.camera_config.copy()

        # If the config has a section named cameras, prefer that.
        if self.camera_config:
            if isinstance(self.camera_config.get('cameras', None), dict):
                self.camera_config = self.camera_config['cameras']
            uids = [self.camera_config[camera]['uid'] for camera in self.camera_config]
            assert len(uids) == len(set(uids)), 'repeated UIDs in the configuration data.'

    def setup(self):
        """Setup custom camera system.

        To be overridden by the subclass if needed. Must return ``self``.

        """

        return self

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
            A dictionary with the camera parameters. If the camera is not
            present in the configuration, returns a simple dictionary with the
            ``name`` or ``uid``.

        """

        assert name or uid, 'either a name or unique identifier are required.'

        if not self.camera_config:
            name = name or uid
            return {'name': name or uid, 'uid': uid}

        if name:
            if name not in self.camera_config:
                return {'name': name or uid, 'uid': uid}

            config_params = {'name': name}
            config_params.update(self.camera_config[name])
            return config_params

        else:
            for name_ in self.camera_config:
                if self.camera_config[name_]['uid'] == uid:
                    config_params = {'name': name_}
                    config_params.update(self.camera_config[name_])
                    return config_params

            name = name or uid
            return {'name': name or uid, 'uid': uid}

    async def start_camera_poller(self, interval=1.):
        """Monitors changes in the camera list.

        Issues calls to `.list_available_cameras` on an interval and compares
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
            self._camera_poller = Poller('camera_poller', self._check_cameras)

        self._camera_poller.start(delay=interval)

        self.log('started camera poller.')

        return self

    async def stop_camera_poller(self):
        """Stops the camera poller if it is running."""

        if self._camera_poller and self._camera_poller.running:
            await self._camera_poller.stop()

    async def _check_cameras(self):
        """Checks the list of connected cameras.

        This is an internal function to be used only by the camera poller.

        """

        try:
            uids = self.list_available_cameras()
        except NotImplementedError:
            self.log('get_connected cameras is not implemented. '
                     'Stopping camera poller.', logging.ERROR)
            # It's important to not do await self.stop_camera_poller()
            # because that would stop the poller from inside the callback
            # and that creates a max recursion error.
            self.loop.create_task(self.stop_camera_poller())
            return False

        # Checks cameras that are handled but not connected.
        to_remove = []
        for camera in self.cameras:
            if camera.uid not in uids and not camera.force:
                self.log(f'camera with UID {camera.uid!r} ({camera.name}) '
                         'is not connected.', logging.INFO)
                to_remove.append(camera.name)

        for camera_name in to_remove:
            await self.remove_camera(camera_name)

        # Checks cameras that are connected but not yet being handled.
        camera_uids = [camera.uid for camera in self.cameras]
        for uid in uids:
            if uid not in camera_uids:
                self.log(f'detected new camera with UID {uid!r}.', logging.INFO)
                await self.add_camera(uid=uid)

    @abc.abstractmethod
    def list_available_cameras(self):
        """Lists the connected cameras as reported by the camera system.

        Returns
        -------
        connected_cameras : `list`
            A list of unique identifiers of cameras connected to the system.

        """

        raise NotImplementedError

    async def add_camera(self, name=None, uid=None, force=False, **kwargs):
        """Adds a new `camera <.BaseCamera>` instance to `.cameras`.

        The configuration values (if any) found in the configuration that
        match the ``name`` or ``uid`` of the camera will be used. These
        parameters can be overridden by providing additional keyword values
        for the corresponding parameters.

        Parameters
        ----------
        name : str
            The name of the camera.
        uid : str
            The unique identifier for the camera.
        force : bool
            Forces the camera to stay in the `.CameraSystem` list even if it
            does not appear in the system camera list.
        kwargs
            Other arguments to be passed to `.BaseCamera` during
            initialisation. These parameters override the default configuration
            where applicable.

        Returns
        -------
        camera
            The new camera instance.

        """

        assert name or uid, 'either name or uid are required.'

        # This returns the camera parameters or a placeholder dict with the
        # name and uid of the camera, if the camera cannot be found in the
        # configuration or there is no configuration whatsoever.
        camera_params = self.get_camera_config(name=name, uid=uid)
        camera_params.update(kwargs)

        name = camera_params.pop('name')
        connected_camera = self.get_camera(name=name, uid=uid)
        if connected_camera:
            self.log(f'camera {name!r} is already connected.', logging.WARNING)
            return connected_camera

        self.log(f'adding camera {name!r} with parameters {camera_params!r}')

        camera = self.camera_class(name, self, force=force, **camera_params)

        # If the autoconnect parameter is set, connects the camera.
        if camera_params.pop('autoconnect', False):
            await camera.connect()

        self.cameras.append(camera)

        # Notify event
        self.notifier.notify(CameraSystemEvent.CAMERA_ADDED, camera_params)

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

                await camera.disconnect()
                self.cameras.remove(camera)

                self.log(f'removed camera {name!r}.')

                # Notify event
                self.notifier.notify(CameraSystemEvent.CAMERA_REMOVED,
                                     {'uid': camera.uid, 'name': camera.name})

                return

        raise ValueError(f'camera {name} is not connected.')

    def get_camera(self, name=None, uid=None):
        """Gets a camera matching a name or UID.

        If only one camera is connected and the method is called without
        arguments, returns the camera.

        Parameters
        ----------
        name : str
            The name of the camera.
        uid : str
            The unique identifier for the camera.

        Returns
        -------
        camera : `.BaseCamera`
            The connected camera (must be one of the cameras in `.cameras`)
            whose name or UID matches the input parameters.

        """

        if name is None and uid is None and len(self.cameras) == 1:
            return self.cameras[0]

        for camera in self.cameras:
            if name and camera.name == name:
                if uid:
                    assert camera.uid == uid, 'camera name does not match uid.'
                return camera
            elif uid and camera.uid == uid:
                return camera

        return False

    def on_camera_connected(self, uid):
        """Event handler for a newly connected camera.

        Parameters
        ----------
        uid : str
            The unique identifier for the camera.

        Returns
        -------
        task : `asyncio.Task`
            The task calling `.add_camera`.

        """

        return self.loop.create_task(self.add_camera(uid=uid))

    def on_camera_disconnected(self, uid):
        """Event handler for a camera that was disconnected.

        Parameters
        ----------
        uid : str
            The unique identifier for the camera.

        Returns
        -------
        task : `asyncio.Task`
            The task calling `.remove_camera`.

        """

        return self.loop.create_task(self.remove_camera(uid=uid))

    async def disconnect(self):
        """Shuts down the system."""

        if self._camera_poller and self._camera_poller.running:
            await self.stop_camera_poller()

    @property
    @abc.abstractmethod
    def __version__(self):
        """The version of the camera library."""

        raise NotImplementedError


class BaseCamera(LoggerMixIn, metaclass=abc.ABCMeta):
    """A base class for wrapping a camera API in a standard implementation.

    Instantiating the `.BaseCamera` class does not open the camera and makes
    it ready to be used. To do that, call and await `.connect`.

    Parameters
    ----------
    name : str
        The name of the camera.
    camera_system : `.CameraSystem` instance
        The camera system handling this camera.
    force : bool
        Forces the camera to stay in the `.CameraSystem` list even if it
        does not appear in the system camera list.
    camera_config : dict
        Parameters used to define how to connect to the camera, its geometry,
        initialisation parameters, etc. The format of the parameters must
        follow the structure of the configuration file.
    image_namer : .ImageNamer or dict
        An instance of `.ImageNamer` used to sequentially assign predefined
        names to new exposure images, or a dictionary of parameters to be
        pased to `.ImageNamer` to create a new instance. If not set, creates
        an image namer with format ``{camera.name}-{num:04d}.fits``.

    Attributes
    ----------
    connected : bool
        Whether the camera is open and connected.
    has_shutter : bool
        Whether the camera has a shutter system.
    auto_shutter : bool
        If `True`, the shutter is automatically handled by the camera firmware
        and it is not necessary to manually open and close the shutter during
        exposures.
    camera_config : dict
        A dictionary with with configuration parameters for the camera. Among
        other, it may contain a section ``connection_params`` which is used by
        `.connect` to open the camera connection.
    fits_model : .FITSModel
        An instance of `.FITSModel` defining the data model of the images
        taken by the camera. If not defined, a basic model will be used.
    image_namer : .ImageNamer
        And instance of `.ImageNamer` to determine the default file path for
        new exposures. If not provided, uses ``'{camera.name}-{num:04d}.fits'``
        where ``camera.name`` is the name of the camera, and ``num`` is a
        sequential counter.

    """

    fits_model = basic_fits_model

    def __init__(self, name, camera_system, force=False, image_namer=None,
                 **camera_config):

        self.name = name

        self.camera_system = camera_system
        self.loop = camera_system.loop

        self.connected = False

        self.has_shutter = camera_config.pop('shutter', False) if camera_config else False
        self.auto_shutter = camera_config.pop('auto_shutter', True) if camera_config else True

        self.force = force
        self.camera_config = camera_config or {}

        self._status = {}

        if isinstance(image_namer, ImageNamer):
            self.image_namer = image_namer
            self.image_namer.camera = self
        elif isinstance(image_namer, dict):
            self.image_namer = ImageNamer(**image_namer, camera=self)
        elif image_namer is None:
            self.image_namer = ImageNamer('{camera.name}-{num:04d}.fits',
                                          dirname='.', overwrite=False,
                                          camera=self)
        else:
            raise CameraError('invalid image_namer parameters.')

        self.__version__ = self.camera_system.__version__

        # Get the same logger as the camera system but uses the UID or name of
        # the camera as prefix for messages from this camera.
        log_header = self.name
        LoggerMixIn.__init__(self, self.camera_system.logger.name,
                             log_header=f'[{log_header.upper()}]: ')

    async def connect(self, force=False, **connection_params):
        """Connects the camera and performs all the necessary setup.

        Parameters
        ----------
        force : bool
            Forces the camera to reconnect even if it's already connected.
        connection_params : dict
            A series of keyword arguments to be passed to the internal
            implementation of ``connect`` for a given camera. If provided,
            they override the ``connection_params`` settings in the
            configuration for this camera.

        """

        if self.connected and not force:
            raise CameraConnectionError('the camera is already connected.')

        camera_connection_params = self.camera_config.get('connection_params', {}).copy()
        camera_connection_params.update(connection_params)

        try:
            await self._connect_internal(**camera_connection_params)
            self.connected = True
            if self.uid is None:
                warnings.warn('camera connected but an UID is not available.', CameraWarning)
        except CameraConnectionError as ee:
            self.connected = False
            self._notify(CameraEvent.CAMERA_CONNECT_FAILED)
            raise CameraConnectionError(f'failed to connect: {ee}')

        self.log('camera connected.')
        self._notify(CameraEvent.CAMERA_CONNECTED)

        return self

    def _notify(self, event, extra_payload=None):
        """Notifies an event."""

        payload = self._get_basic_payload()
        payload.update(extra_payload or {})

        self.camera_system.notifier.notify(event, payload)

    def _get_basic_payload(self):
        """Returns a dictionary with basic payload for notifying events."""

        return {'uid': self.uid, 'name': self.name, 'camera': self}

    @abc.abstractmethod
    async def _connect_internal(self, **connection_params):
        """Internal method to connect the camera.

        Must raise `.CameraConnectionError` if the connection fails.

        """

        raise NotImplementedError

    @property
    def _uid_internal(self):
        """Get the unique identifier from the camera (e.g., serial number).

        This method can be internally overridden to return the UID of the
        camera by calling the internal camera firmware.

        Returns
        -------
        uid : str
            The unique identifier for this camera.

        """

        return None

    @property
    def uid(self):
        """Returns the unique identifier of the camera.

        Calls `._uid_internal` to get the unique identifier directly from the
        camera firmware. Otherwise, returns the UID from the configuration, or
        `None` if not defined.

        """

        uid_from_camera = self._uid_internal
        uid_from_config = self.camera_config.get('uid', None)

        if uid_from_camera and uid_from_config:
            assert uid_from_camera == uid_from_config, 'mismatch between config and camera UID.'
            return uid_from_camera
        elif uid_from_camera:
            return uid_from_camera
        else:
            return uid_from_config

    def get_status(self, update=False):
        """Returns a dictionary with the camera status values.

        Parameters
        ----------
        update : bool
            If `True`, retrieves the status from the camera; otherwise returns
            the last cached status.

        """

        if update or not self._status:
            self._status = self._status_internal()

        return self._status

    def _status_internal(self):
        """Gets a dictionary with the status of the camera.

        This method is intended to be overridden by the specific camera.

        Returns
        -------
        status : `dict`
            A dictionary with status values from the camera (e.g.,
            temperature, cooling status, firmware information, etc.)

        """

        return {}

    async def expose(self, exptime, image_type='object',
                     stack=1, stack_function=numpy.median,
                     fits_model=None, filename=None,
                     write=False, **kwargs):
        """Exposes the camera.

        This is the general method to expose the camera. It receives the
        exposure time and type of exposure, along with other necessary
        arguments, and returns an `.Exposure` instance with the data and
        metadata for the image.

        The `.Exposure` object is created and populated by `.expose` and passed
        to the parent mixins for the camera class. It is also passed to the
        internal expose method where the concrete implementation of the camera
        expose system happens.

        Parameters
        ----------
        exptime : float
            The exposure time for the image, in seconds.
        image_type : str
            The type of image (``{'bias', 'dark', 'object', 'flat'}``).
        stack : int
            Number of images to stack.
        stack_function
            The function to apply to the several images taken to generate the
            final stacked image. Defaults to the median.
        fits_model : .FITSModel
            A `.FITSModel` that can be used to override the default model
            for the camera.
        filename : str
            The path where to write the image. If not given, a new name is
            automatically assigned based on the camera instance of
            `.ImageNamer`.
        write : bool
            If `True`, writes the image to disk immediately.
        kwargs : dict
            Other keyword arguments to pass to the internal expose method.

        Returns
        -------
        exposure : `.Exposure`
            An `.Exposure` object containing the image data, exposure time,
            and header datamodel.

        """

        exptime = exptime or 0.0

        if exptime < 0:
            raise ExposureError('exposure time cannot be < 0')

        if image_type == 'bias' and exptime > 0:
            warnings.warn('setting exposure time for bias to 0', ExposureWarning)
            exptime = 0.

        exposures = []

        for __ in range(stack):

            exposure = Exposure(self, fits_model=(fits_model or self.fits_model))
            exposure.image_type = image_type
            exposure.exptime = exptime

            try:
                await self._expose_internal(exposure, **kwargs)
            except ExposureError as e:
                self._notify(CameraEvent.EXPOSURE_FAILED, {'error': str(e)})
                raise

            if exposure.data is None:
                error = 'data was not taken.'
                self._notify(CameraEvent.EXPOSURE_FAILED, {'error': error})
                raise ExposureError(error)

            exposures.append(exposure)

        if len(exposures) > 1:
            data = [exp.data for exp in exposures]
            stacked_data = stack_function(numpy.stack(data), axis=0)
            exposures[0].data = stacked_data

        exposure = exposures[0]
        exposure.exptime_n = exptime * stack
        exposure.stack = stack
        exposure.stack_function = stack_function.__name__

        exposure.filename = filename or self.image_namer()

        self._notify(CameraEvent.EXPOSURE_READ)

        if write:
            self._notify(CameraEvent.EXPOSURE_WRITING)
            await self.loop.run_in_executor(None, exposure.write)
            self._notify(CameraEvent.EXPOSURE_WRITTEN)

        return exposure

    @abc.abstractmethod
    async def _expose_internal(self, exposure, **kwargs):
        """Internal method to handle camera exposures.

        This method handles the entire process of exposing and reading the
        camera and return an array or FITS object with the exposed frame.
        If necessary, it must handle the correct operation of the shutter
        before and after the exposure, for example ::

            if self.has_shutter and not self.auto_shutter:
                if image_type in ['bias', 'dark']:
                    await self.set_shutter(False)
                else:
                    await self.set_shutter(True)

        It receives an `.Exposure` instance in which the exposure time,
        image type, and other parameters have been set by `.expose`.
        Additional parameters can be passed via the ``kwargs`` arguments.
        The camera instance can be accessed via the ``Exposure.camera``
        attribute.

        The method is responsible for adding any relevant attributes in the
        exposure instance. The time of the start of the exposure is initially
        set just before `._expose_internal` is called, but if necessary it
        must be updated when the camera is actually commanded to expose (or,
        if flushing occurs, when the integration starts). Finally, it must
        set ``Exposure.data`` with the image as a Numpy array.

        Parameters
        ----------
        exposure : .Exposure
            The exposure being taken.
        kwargs : dict
            Other keyword arguments to configure the exposure.

        """

        raise NotImplementedError

    async def disconnect(self):
        """Shuts down the camera."""

        try:
            await self._disconnect_internal()
        except CameraConnectionError as ee:
            self._notify(CameraEvent.CAMERA_DISCONNECT_FAILED)
            raise CameraConnectionError(f'failed to disconnect: {ee}')

        self.log('camera has been disconnected.')
        self._notify(CameraEvent.CAMERA_DISCONNECTED)

        return True

    async def _disconnect_internal(self):
        """Internal method to disconnect a camera.

        Must raise a `.CameraConnectionError` if the shutdown fails.

        """

        raise NotImplementedError
