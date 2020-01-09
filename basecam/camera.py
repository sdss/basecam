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

import astropy.time
import numpy
from astropy.io import fits
from sdsstools import read_yaml_file

from .events import CameraEvent, CameraSystemEvent
from .exceptions import CameraError
from .fits import create_fits_image
from .helpers import LoggerMixIn, Poller
from .notifier import EventNotifier

__all__ = ['CameraSystem', 'BaseCamera', 'VirtualCamera']


class ExposureFlavourMixIn(object):
    """Methods to take exposures with different flavours."""

    async def bias(self, *args, **kwargs):
        """Take a bias image."""

        kwargs.pop('flavour', None)
        kwargs.pop('shutter', None)

        return await self.expose(*args, 0.0, shutter=False, flavour='bias', **kwargs)

    async def dark(self, *args, **kwargs):
        """Take a dark image."""

        kwargs.pop('flavour', None)
        kwargs.pop('shutter', None)

        return await self.expose(*args, shutter=False, flavour='dark', **kwargs)

    async def flat(self, *args, **kwargs):
        """Take a flat image."""

        kwargs.pop('flavour', None)
        kwargs.pop('shutter', None)

        return await self.expose(*args, shutter=True, flavour='flat', **kwargs)

    async def science(self, *args, **kwargs):
        """Take a science image."""

        kwargs.pop('flavour', None)
        kwargs.pop('shutter', None)

        return await self.expose(*args, shutter=True, flavour='object', **kwargs)


class CameraSystem(LoggerMixIn):
    """A base class for the camera system.

    Provides an abstract class for the camera system, including camera
    connection/disconnection event handling, adding and removing cameras, etc.

    While the instance does not handle the loop, it assumes that an event loop
    is running elsewhere, for example via `asyncio.loop.run_forever`.

    Parameters
    ----------
    camera_class : .BaseCamera subclass
        The subclass of `.BaseCamera` to use with this camera system.
    config : dict or path
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

    def __init__(self, camera_class, config=None, logger_name=None,
                 log_header=None, loop=None):

        assert issubclass(camera_class, BaseCamera) and camera_class != BaseCamera, \
            'camera_class must be a subclass of BaseCamera.'

        self.camera_class = camera_class

        logger_name = logger_name or self.__class__.__name__.upper()
        log_header = log_header or f'[{logger_name.upper()}]: '

        LoggerMixIn.__init__(self, logger_name, log_header=log_header)

        self.config = config
        self.config_file = None

        self.loop = loop or asyncio.get_event_loop()

        #: list: The list of cameras being handled.
        self.cameras = []

        self._camera_poller = None

        #: .EventNotifier: Notifies of `.CameraSystemEvent` and `.CameraEvent` events.
        self.notifier = EventNotifier()

        if config is None:
            self.config = config
        elif config and not isinstance(config, dict):
            self.config_file = config
            self.config = read_yaml_file(self.config)
            self.log(f'read configuration file from {self.config_file}')
        else:
            self.config = self.config.copy()

        # If the config has a section named cameras, prefer that.
        if isinstance(self.config.get('cameras', None), dict):
            self.config = self.config['cameras']

    def setup(self):
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
            A dictionary with the camera parameters. If the camera is not
            present in the configuration, returns a simple dictionary with the
            ``name`` or ``uid``.

        """

        assert name or uid, 'either a name or unique identifier are required.'

        if not self.config:
            name = name or uid
            return {'name': name or uid, 'uid': uid}

        if name:
            if name not in self.config:
                return {'name': name or uid, 'uid': uid}

            config_params = {'name': name}
            config_params.update(self.config[name])
            return config_params

        else:
            for name_ in self.config:
                if self.config[name_]['uid'] == uid:
                    config_params = {'name': name_}
                    config_params.update(self.config[name_])
                    return config_params

            name = name or uid
            return {'name': name or uid, 'uid': uid}

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
            uids = self.get_connected_cameras()
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

    def get_connected_cameras(self):
        """Lists the connected cameras as reported by the camera system.

        This method should not be confused with `.cameras`, which lists the
        `.BaseCamera` instance currently being handled by the `.CameraSystem`.
        `.get_connected_cameras` returns the cameras that the camera API
        believes are available at any given time. While both lists are likely
        to match if the camera poller or camera event handling is used, it does
        not need to be the case if cameras are being handled manually.

        Returns
        -------
        connected_cameras : `list`
            A list of unique identifiers of the connected cameras. The unique
            identifiers must match those in the configuration file.

        """

        raise NotImplementedError

    async def add_camera(self, name=None, uid=None, force=False, **kwargs):
        """Adds a new `.Camera` instance to `.cameras`.

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
        connected_camera = self.get_camera(name)
        if connected_camera:
            self.log(f'camera {name!r} is already connected.', logging.WARNING)
            return connected_camera

        self.log(f'adding camera {name!r} with parameters {camera_params!r}')

        camera = self.camera_class(name, self, force=force, **camera_params)

        # If the autoconnect parameter is set, connects the camera.
        connection_params = camera_params.get('connection_params', {})
        if connection_params.pop('autoconnect', True):
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

                await camera.shutdown()
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

    async def shutdown(self):
        """Shuts down the system."""

        if self._camera_poller and self._camera_poller.running:
            await self.stop_camera_poller()


class BaseCamera(LoggerMixIn, ExposureFlavourMixIn, metaclass=abc.ABCMeta):
    """A base class for wrapping a camera API in a standard implementation.

    Instantiating the `.Camera` class does not open the camera and makes
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
    config_params : dict
        Parameters used to define how to connect to the camera, its geometry,
        initialisation parameters, etc. The format of the parameters must
        follow the structure of the configuration file.

    """

    def __init__(self, name, camera_system, force=False, **config_params):

        self.name = name

        self.camera_system = camera_system

        self.connected = False

        self.has_shutter = config_params.pop('shutter', False)
        self.manual_shutter = config_params.pop('manual_shutter', True)

        self.force = force
        self.config_params = config_params

    async def connect(self, **user_config_params):
        """Connects the camera and performs all the necessary setup.

        Parameters
        ----------
        user_config_params : dict
            A series of keyword arguments that override the configuration
            parameters defined during the object instantiation.

        """

        self.config_params.update(user_config_params)

        await self._connect_internal(**self.config_params)
        self.connected = True

        # Get the same logger as the camera system but uses the UID or name of
        # the camera as prefix for messages from this camera.
        log_header = self.uid or self.name
        LoggerMixIn.__init__(self, self.camera_system.logger.name,
                             log_header=f'[{log_header.upper()}]: ')

        self.log('camera connected.')
        self._notify(CameraEvent.CAMERA_OPEN)

        return self

    def _notify(self, event, payload=None):
        """Notifies an event."""

        payload = payload or self._get_basic_payload()
        self.camera_system.notifier.notify(event, payload)

    def _get_basic_payload(self):
        """Returns a dictionary with basic payload for notifying events."""

        return {'uid': self.uid, 'name': self.name}

    @abc.abstractmethod
    async def _connect_internal(self, **config_params):
        """Internal method to connect the camera."""

        pass

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
        uid_from_config = self.config_params.get('uid', None)

        if uid_from_camera and uid_from_config:
            assert uid_from_camera == uid_from_config, 'mismatch between config and camera UID.'
            return uid_from_camera
        elif uid_from_camera:
            return uid_from_camera
        else:
            return uid_from_config

    async def get_status(self):
        """Returns a dictionary with the camera status values."""

        return await self._status_internal()

    @abc.abstractmethod
    async def _status_internal(self):
        """Gets a dictionary with the status of the camera.

        This method is intended to be overridden by the specific camera.

        Returns
        -------
        status : dict
            A dictionary with status values from the camera (e.g.,
            temperature, cooling status, firmware information, etc.)

        """

        pass

    async def expose(self, exposure_time, flavour='object', shutter=True, header=None):
        """Exposes the camera.

        This is a general method to expose the camera. Other methods such as
        `.bias` or `.dark` ultimately call `.expose` with the appropriate
        parameters.

        Parameters
        ----------
        exposure_time : float
            The exposure time of the image.
        flavour : str
            The type of image.
        shutter : bool
            Whether to open the shutter while exposing (`True`) or not
            (`False`).
        header : ~astropy.io.fits.Header or dict
            Keyword pairs (as a dictionary or astropy
            `~astropy.io.fits.Header`) to be added to the image header.

        Returns
        -------
        fits : `astropy.io.fits.HDUList`
            An `astropy.io.fits.HDUList` object with a single extension
            containing the image data and header.

        """

        # Commands the shutter
        if self.has_shutter and self.manual_shutter:
            await self.set_shutter(shutter)

        self._notify(CameraEvent.EXPOSURE_STARTED)

        # Takes the image.
        image = await self._expose_internal(exposure_time)

        if not isinstance(image, fits.HDUList):
            image = create_fits_image(image, exposure_time)

        image[0].header.update(
            {
                'IMAGETYP': (flavour.upper(), 'Image type'),
                'CAMNAME': (self.name.upper(), 'Name of the camera'),
            }
        )

        self._notify(CameraEvent.EXPOSURE_DONE)

        # Closes the shutter
        if self.has_shutter and self.manual_shutter:
            await self.set_shutter(False)

        return image

    @abc.abstractmethod
    async def _expose_internal(self, exposure_time):
        """Internal method to handle camera exposures.

        Returns
        -------
        fits : `~astropy.io.fits.HDUList`
            An HDU list with a single extension containing the image data
            and header.

        """

        pass

    async def _set_shutter_internal(self, shutter_open):
        """Internal method to set the position of the shutter."""

        raise NotImplementedError

    async def _get_shutter_internal(self):
        """Internal method to get the position of the shutter."""

        raise NotImplementedError

    async def set_shutter(self, shutter, force=False):
        """Sets the position of the shutter.

        Parameters
        ----------
        shutter : bool
            If `True` moves the shutter open, otherwise closes it.
        force : bool
            Normally, a call is made to `.get_shutter` to determine if the
            shutter is already in the commanded position. If it is, the
            shutter is not commanded to move. ``force=True`` sends the
            move command regardless of the internal status of the shutter.

        """

        if not self.has_shutter:
            return

        current_status = await self.get_shutter()
        if current_status == shutter and not force:
            return

        return await self._set_shutter_internal(shutter)

    async def open_shutter(self):
        """Opens the shutter (alias for ``set_shutter(True)``)."""

        return await self.set_shutter(True)

    async def close_shutter(self):
        """Opens the shutter (alias for ``set_shutter(False)``)."""

        return await self.set_shutter(False)

    async def get_shutter(self):
        """Gets the position of the shutter."""

        if not self.has_shutter:
            raise CameraError('camera {self.name!r} does not have a shutter.')

        return await self._get_shutter_internal()

    async def shutdown(self):
        """Shuts down the camera."""

        await self._disconnect_internal()

        self.log('camera has been disconnected.')
        self._notify(CameraEvent.CAMERA_CLOSED)

    @abc.abstractmethod
    async def _disconnect_internal(self):
        """Internal method to disconnect a camera."""

        pass


class VirtualCamera(BaseCamera):
    """A virtual camera that does not require hardware.

    This class is mostly intended for testing and development. It behaves
    in all ways as a real camera with pre-defined responses that depend on the
    input parameters.

    """

    # Sets the internal UID for the camera.
    _uid = 'DEV_12345'

    def __init__(self, *args, **kwargs):

        self._shutter_position = False

        self.width = 640
        self.height = 480

        super().__init__(*args, **kwargs)

    async def _connect_internal(self, **config_params):
        return True

    @property
    def _uid_internal(self):
        return self._uid

    async def _status_internal(self):
        return {'temperature': 25.,
                'cooler': 10.}

    async def _expose_internal(self, exposure_time):

        # Creates a spiral pattern
        xx = numpy.arange(-5, 5, 0.1)
        yy = numpy.arange(-5, 5, 0.1)
        xg, yg = numpy.meshgrid(xx, yy, sparse=True)
        tile = numpy.sin(xg**2 + yg**2) / (xg**2 + yg**2)

        # Repeats the tile to match the size of the image.
        data = numpy.tile(tile.astype(numpy.uint16),
                          (self.height // len(yy) + 1, self.width // len(yy) + 1))
        data = data[0:self.height, 0:self.width]

        obstime = astropy.time.Time('2000-01-01 00:00:00')

        fits_image = create_fits_image(data, exposure_time, obstime=obstime)

        return fits_image

    async def _set_shutter_internal(self, shutter_open):
        self._shutter_position = shutter_open

    async def _get_shutter_internal(self):
        return self._shutter_position

    async def _disconnect_internal(self):
        pass
