#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-06-19
# @Filename: camera.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import abc
import asyncio
import logging
import os
import pathlib
import time
import warnings
from logging import INFO, WARNING

from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Type,
    TypeVar,
    Union,
    cast,
)

import numpy

from sdsstools import get_logger, read_yaml_file
from sdsstools.logger import SDSSLogger

from basecam.models.fits import FITSModel

from .events import CameraEvent, CameraSystemEvent
from .exceptions import (
    CameraConnectionError,
    CameraError,
    ExposureError,
    ExposureWarning,
)
from .exposure import Exposure, ImageNamer
from .models import basic_fits_model
from .notifier import EventNotifier
from .utils import LoggerMixIn, Poller


try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal


__all__ = ["CameraSystem", "BaseCamera"]


AnyPath = Union[str, pathlib.Path]
_T_CameraSystem = TypeVar("_T_CameraSystem", bound="CameraSystem")
_T_BaseCamera = TypeVar("_T_BaseCamera", bound="BaseCamera")


class CameraSystem(LoggerMixIn, Generic[_T_BaseCamera], metaclass=abc.ABCMeta):
    """A base class for the camera system.

    Provides an abstract class for the camera system, including camera
    connection/disconnection event handling, adding and removing cameras, etc.

    While the instance does not handle the loop, it assumes that an event loop
    is running elsewhere, for example via `asyncio.loop.run_forever`.

    Parameters
    ----------
    camera_class
        The subclass of `.BaseCamera` to use with this camera system.
    camera_config
        A dictionary with the configuration parameters for the multiple
        cameras that can be present in the system, or the path to a YAML file.
        Refer to the documentation for details on the accepted format.
    include
        List of camera UIDs that can be connected.
    exclude
        List of camera UIDs that will be ignored.
    logger
        The logger instance to use. If `None`, a new logger will be created.
    log_header
        A string to be prefixed to each message logged.
    log_file
        The path to which to log. If set, the log will be saved to that file path.
    verbose
        Logging level for the console handler  If `False`, only warnings and errors
        will be logged to the console.
    """

    camera_class: Union[Type[_T_BaseCamera], None] = None
    include = None
    exclude = None

    def __init__(
        self,
        camera_class: Optional[Type[_T_BaseCamera]] = None,
        camera_config: Optional[Union[AnyPath, Dict[str, Any]]] = None,
        include: Optional[List[Any]] = None,
        exclude: Optional[List[Any]] = None,
        logger: Optional[SDSSLogger] = None,
        log_header: Optional[str] = None,
        log_file: Optional[AnyPath] = None,
        verbose: Optional[Union[bool, int]] = False,
    ):

        self.camera_class = camera_class or self.camera_class

        if not self.camera_class or not issubclass(self.camera_class, BaseCamera):
            raise ValueError("camera_class must be a subclass of BaseCamera.")

        self.include = self.include or include
        self.exclude = self.exclude or exclude

        logger_name = self.__class__.__name__.upper()
        self.log_header = log_header or f"[{logger_name.upper()}]: "
        self.logger = logger or cast(SDSSLogger, get_logger(logger_name))

        if verbose:
            self.logger.sh.setLevel(int(verbose))
        else:
            self.logger.sh.setLevel(logging.WARNING)

        if log_file:
            self.logger.start_file_logger(str(log_file))
            if self.logger.fh:
                assert self.logger.fh.formatter
                self.logger.fh.formatter.converter = time.gmtime
                self.log(f"logging to {log_file}")

        self.loop = asyncio.get_event_loop()
        self.loop.set_exception_handler(self.logger.asyncio_exception_handler)

        #: list: The list of cameras being handled.
        self.cameras: List[_T_BaseCamera] = []

        self._camera_poller = None

        #: .EventNotifier: Notifies of `.CameraSystemEvent` and `.CameraEvent` events.
        self.notifier = EventNotifier()

        self._config: Optional[Dict[str, Any]] = None

        if camera_config:
            if isinstance(camera_config, dict):
                self._config = camera_config.copy()
            else:
                self._config = cast(Dict[str, Any], read_yaml_file(str(camera_config)))
                self.log(f"read configuration file from {camera_config}")

        # If the config has a section named "cameras", prefer that.
        if self._config is not None:
            if isinstance(self._config.get("cameras", None), dict):
                self._config = self._config["cameras"]
            assert self._config is not None
            uids = [self._config[camera]["uid"] for camera in self._config]
            if len(uids) != len(set(uids)):
                raise ValueError("repeated UIDs in the configuration data.")

        self.running: bool = False

    def setup(self):
        """Setup custom camera system.

        To be overridden by the subclass if needed. Must return ``self``.
        """

        self.running = True
        return self

    def get_camera_config(
        self,
        name: Optional[str] = None,
        uid: Optional[str] = None,
    ) -> Union[Dict[str, Any], None]:
        """Gets camera parameters from the configuration.

        Parameters
        ----------
        name
            The name of the camera.
        uid
            The unique identifier of the camera.

        Returns
        -------
        camera_params
            A dictionary with the camera parameters. If the camera is not
            present in the configuration, returns `None`.
        """

        assert name or uid, "either a name or unique identifier are required."

        if not self._config:
            return None

        if name:
            if name not in self._config:
                return None

            config_params = {"name": name}
            config_params.update(self._config[name])
            return config_params

        else:
            for name_ in self._config:
                if self._config[name_]["uid"] == uid:
                    config_params = {"name": name_}
                    config_params.update(self._config[name_])
                    return config_params

            return None

    async def start_camera_poller(
        self: _T_CameraSystem,
        interval: float = 1.0,
    ) -> _T_CameraSystem:
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
        interval
            Interval, in seconds, on which the connected cameras are polled
            for changes.
        """

        if self._camera_poller is None:
            self._camera_poller = Poller("camera_poller", self._check_cameras)

        self._camera_poller.start(delay=interval)

        self.log("started camera poller.")

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
            self.log(f"List cameras returned: {uids}", logging.DEBUG)
        except NotImplementedError:
            self.log(
                "get_connected cameras is not implemented. Stopping camera poller.",
                logging.ERROR,
            )
            # It's important to not do await self.stop_camera_poller()
            # because that would stop the poller from inside the callback
            # and that creates a max recursion error.
            self.loop.create_task(self.stop_camera_poller())
            return False

        # Checks cameras that are handled but not connected.
        to_remove = []
        for camera in self.cameras:
            if camera.uid not in uids and not camera.force:
                self.log(
                    f"camera with UID {camera.uid!r} ({camera.name}) has been removed.",
                    logging.INFO,
                )
                to_remove.append(camera.name)

        for camera_name in to_remove:
            await self.remove_camera(camera_name)

        # Checks cameras that are connected.
        camera_uids = [camera.uid for camera in self.cameras]
        for uid in uids:
            if uid in camera_uids:
                continue
            elif self.include and uid not in self.include:
                continue
            elif self.exclude and uid in self.exclude:
                continue
            else:
                self.log(f"detected new camera with UID {uid!r}.", INFO)
                await self.add_camera(uid=uid)

    @abc.abstractmethod
    def list_available_cameras(self) -> List[str]:
        """Lists the connected cameras as reported by the camera system.

        Returns
        -------
        connected_cameras
            A list of unique identifiers of cameras connected to the system.
        """

        raise NotImplementedError

    async def add_camera(
        self,
        name: Optional[str] = None,
        uid: Optional[str] = None,
        force: bool = False,
        autoconnect: bool = True,
        **kwargs,
    ) -> BaseCamera:
        """Adds a new `camera <.BaseCamera>` instance to `.cameras`.

        The configuration values (if any) found in the configuration that
        match the ``name`` or ``uid`` of the camera will be used. These
        parameters can be overridden by providing additional keyword values
        for the corresponding parameters.

        Parameters
        ----------
        name
            The name of the camera.
        uid
            The unique identifier for the camera.
        force
            Forces the camera to stay in the `.CameraSystem` list even if it
            does not appear in the system camera list.
        autoconnect
            Whether to autoconnect the camera.
        kwargs
            Other arguments to be passed to `.BaseCamera` during
            initialisation. These parameters override the default configuration
            where applicable.

        Returns
        -------
        camera
            The new camera instance.
        """

        assert name or uid, "either name or uid are required."

        camera_params = self.get_camera_config(name=name, uid=uid) or {}
        camera_params.update(kwargs)

        # At this point we do need to have an UID, either passed directly to
        # add_camera or from the configuration.
        uid = camera_params.get("uid", uid)

        if not uid:
            raise CameraError(
                "No camera UID provided or found in "
                f"the configuration for camera {name!r}."
            )

        name = camera_params.pop("name", uid)
        connected_camera = self.get_camera(name=name, uid=uid)
        if connected_camera:
            self.log(f"camera {name!r} is already connected.", WARNING)
            return connected_camera

        self.log(f"adding camera {name!r} with parameters {camera_params!r}")

        assert self.camera_class
        camera = self.camera_class(
            uid, self, name=name, force=force, camera_params=camera_params
        )

        # If the autoconnect parameter is set, connects the camera.
        if autoconnect and camera_params.pop("autoconnect", True):
            await camera.connect()
        else:
            self.log(f"camera {name!r} added but not connected.")

        self.cameras.append(camera)

        # Notify event
        self.notifier.notify(CameraSystemEvent.CAMERA_ADDED, camera_params)

        return camera

    async def remove_camera(
        self,
        name: Optional[str] = None,
        uid: Optional[str] = None,
    ):
        """Removes a camera, cancelling any ongoing process.

        Parameters
        ----------
        name
            The name of the camera.
        uid
            The unique identifier for the camera.
        """

        for camera in self.cameras:
            if camera.name == name or camera.uid == uid:

                await camera.disconnect()
                self.cameras.remove(camera)

                self.log(f"removed camera {camera.name!r}.")

                # Notify event
                self.notifier.notify(
                    CameraSystemEvent.CAMERA_REMOVED,
                    {"uid": camera.uid, "name": camera.name},
                )

                return

        raise ValueError(f"camera {name} is not connected.")

    def get_camera(
        self,
        name: Optional[str] = None,
        uid: Optional[str] = None,
    ) -> Union[BaseCamera, Literal[False]]:
        """Gets a camera matching a name or UID.

        If only one camera is connected and the method is called without
        arguments, returns the camera.

        Parameters
        ----------
        name
            The name of the camera.
        uid
            The unique identifier for the camera.

        Returns
        -------
        camera
            The connected camera (must be one of the cameras in `.cameras`)
            whose name or UID matches the input parameters. Returns `False` if the
            camera was not found.
        """

        if name is None and uid is None and len(self.cameras) == 1:
            return self.cameras[0]

        for camera in self.cameras:
            if name and camera.name == name:
                if uid:
                    assert camera.uid == uid, "camera name does not match uid."
                return camera
            elif uid and camera.uid == uid:
                return camera

        return False

    def on_camera_connected(self, uid: str) -> asyncio.Task[BaseCamera]:
        """Event handler for a newly connected camera.

        Parameters
        ----------
        uid
            The unique identifier for the camera.

        Returns
        -------
        task
            The task calling `.add_camera`.
        """

        return self.loop.create_task(self.add_camera(uid=uid))

    def on_camera_disconnected(self, uid: str) -> asyncio.Task[None]:
        """Event handler for a camera that was disconnected.

        Parameters
        ----------
        uid
            The unique identifier for the camera.

        Returns
        -------
        task
            The task calling `.remove_camera`.

        """

        return self.loop.create_task(self.remove_camera(uid=uid))

    async def disconnect(self):
        """Shuts down the system."""

        if self._camera_poller and self._camera_poller.running:
            await self.stop_camera_poller()

        self.running = False

    @property
    @abc.abstractmethod
    def __version__(self) -> str:
        """The version of the camera library."""

        raise NotImplementedError


class BaseCamera(LoggerMixIn, metaclass=abc.ABCMeta):
    """A base class for wrapping a camera API in a standard implementation.

    Instantiating the `.BaseCamera` class does not open the camera and makes
    it ready to be used. To do that, call and await `.connect`.

    Parameters
    ----------
    uid
        The unique identifier for the camera.
    camera_system
        The camera system handling this camera.
    name
        The name of the camera. If not set, the ``uid`` will be used.
    force
        Forces the camera to stay in the `.CameraSystem` list even if it
        does not appear in the system camera list.
    image_namer
        An instance of `.ImageNamer` used to sequentially assign predefined
        names to new exposure images, or a dictionary of parameters to be
        passed to `.ImageNamer` to create a new instance. If not set, creates
        an image namer with format ``{camera.name}-{num:04d}.fits``.
    camera_params
        Parameters used to define how to connect to the camera, its geometry,
        initialisation parameters, etc. The format of the parameters must
        follow the structure of the configuration file.

    Attributes
    ----------
    connected : bool
        Whether the camera is open and connected.
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
    image_namer = ImageNamer(
        "{camera.name}-{num:04d}.fits",
        dirname=".",
        overwrite=False,
    )

    def __init__(
        self,
        uid: str,
        camera_system: CameraSystem,
        name: Optional[str] = None,
        force: bool = False,
        image_namer: Optional[Union[ImageNamer, dict]] = None,
        camera_params={},
    ):

        self.uid = uid
        self.name = name or self.uid

        self.camera_system = camera_system
        self.loop = camera_system.loop

        self.connected = False

        self.force = force

        self.camera_params = camera_params
        if "uid" in camera_params and camera_params["uid"] != self.uid:
            raise CameraError("Mismatching UIDs between input and camera parameters.")

        self._status = {}

        if isinstance(image_namer, ImageNamer):
            self.image_namer = image_namer
            self.image_namer.camera = self
        elif isinstance(image_namer, dict):
            self.image_namer = ImageNamer(**image_namer, camera=self)
        elif image_namer is None:
            pass
        else:
            raise CameraError(f"Invalid image namer {image_namer!r}")

        self.image_namer.camera = self
        self.__version__ = self.camera_system.__version__

        # Get the same logger as the camera system but use the UID or
        # name of the camera as prefix for messages from this camera.
        self.log_header = f"[{self.name.upper()}]: "
        self.logger = self.camera_system.logger

    async def connect(
        self: _T_BaseCamera,
        force: bool = False,
        **kwargs,
    ) -> _T_BaseCamera:
        """Connects the camera and performs all the necessary setup.

        Parameters
        ----------
        force
            Forces the camera to reconnect even if it's already connected.
        kwargs
            A series of keyword arguments to be passed to the internal
            implementation of ``connect`` for a the camera. If provided,
            they override the ``connection`` settings in the
            configuration for this camera.
        """

        if self.connected and not force:
            raise CameraConnectionError("the camera is already connected.")

        conn_params = self.camera_params.get("connection", {}).copy()
        conn_params.update(kwargs)

        try:
            await self._connect_internal(**conn_params)
            self.connected = True
        except CameraConnectionError as ee:
            self.connected = False
            self.notify(CameraEvent.CAMERA_CONNECT_FAILED)
            raise CameraConnectionError(f"failed to connect: {ee}")

        self.log("camera connected.")
        self.notify(CameraEvent.CAMERA_CONNECTED)

        return self

    def notify(
        self,
        event: CameraEvent,
        extra_payload: Optional[Dict[str, Any]] = None,
    ):
        """Notifies an event."""

        payload = self._get_basic_payload()
        payload.update(extra_payload or {})

        self.camera_system.notifier.notify(event, payload)

    def _get_basic_payload(self) -> Dict[str, Any]:
        """Returns a dictionary with basic payload for notifying events."""

        return {"uid": self.uid, "name": self.name, "camera": self}

    @abc.abstractmethod
    async def _connect_internal(self, **conn_params):
        """Internal method to connect the camera.

        Must raise `.CameraConnectionError` if the connection fails.
        """

        raise NotImplementedError

    @property
    def status(self):
        """Returns the cached status. Equivalent to ``get_status(update=False)``."""
        return self.get_status(update=False)

    def get_status(self, update: bool = False) -> Dict[str, Any]:
        """Returns a dictionary with the camera status values.

        Parameters
        ----------
        update
            If `True`, retrieves the status from the camera; otherwise returns
            the last cached status.
        """

        if update or not self._status:
            try:
                self._status = self._status_internal()
            except Exception as err:
                self.log(f"Failed to receive status: {err}", WARNING)
                self._status = {}

        return self._status

    def _status_internal(self) -> Dict[str, Any]:
        """Gets a dictionary with the status of the camera.

        This method is intended to be overridden by the specific camera.

        Returns
        -------
        status
            A dictionary with status values from the camera (e.g.,
            temperature, cooling status, firmware information, etc.)
        """

        return {}

    async def expose(
        self,
        exptime: float,
        image_type: str = "object",
        stack: int = 1,
        stack_function: Callable[..., numpy.ndarray] = numpy.median,
        fits_model: Optional[FITSModel] = None,
        filename: Optional[str] = None,
        num: Optional[int] = None,
        write: bool = False,
        postprocess: bool = True,
        **kwargs,
    ) -> Exposure:
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
        exptime
            The exposure time for the image, in seconds.
        image_type
            The type of image (``{'bias', 'dark', 'object', 'flat'}``).
        stack
            Number of images to stack.
        stack_function
            The function to apply to the several images taken to generate the
            final stacked image. Defaults to the median.
        fits_model
            A `.FITSModel` that can be used to override the default model
            for the camera.
        filename
            The path where to write the image. If not given, a new name is
            automatically assigned based on the camera instance of
            `.ImageNamer`.
        num
            If specified, a ``num`` value to pass wot `.ImageNamer` to define
            the sequence number of the exposure filename.
        write
            If `True`, writes the image to disk immediately.
        postprocess
            Whether to run the post-process stage. This argument is ignored if the
            subclass of `.BaseCamera` does not override ``_post_process_internal``.
        kwargs
            Other keyword arguments to pass to the internal expose and post-process
            methods.

        Returns
        -------
        exposure
            An `.Exposure` object containing the image data, exposure time,
            and header datamodel.
        """

        exptime = exptime or 0.0
        fits_model = fits_model or self.fits_model

        if exptime < 0:
            raise ExposureError("exposure time cannot be < 0")

        if image_type == "bias" and exptime > 0:
            warnings.warn("setting exposure time for bias to 0", ExposureWarning)
            exptime = 0.0

        exposures: List[Exposure] = []

        notif_payload = {
            "exptime": exptime,
            "remaining_time": exptime,
            "image_type": image_type,
            "n_stack": stack,
            "current_stack": 1,
        }

        for idx in range(stack):

            notif_payload.update({"n_stack": idx + 1})

            exposure = Exposure(self, fits_model=fits_model)
            exposure.image_type = image_type
            exposure.exptime = exptime

            self.notify(CameraEvent.EXPOSURE_INTEGRATING, notif_payload)
            try:
                await self._expose_internal(exposure, **kwargs)
            except Exception as err:
                self.notify(CameraEvent.EXPOSURE_FAILED, {"error": str(err)})
                raise ExposureError(str(err))

            if exposure.data is None:
                error = "data was not taken."
                self.notify(CameraEvent.EXPOSURE_FAILED, {"error": error})
                raise ExposureError(error)

            exposures.append(exposure)

        if len(exposures) > 1:
            data = [cast(numpy.ndarray, exp.data) for exp in exposures]
            stacked_data = stack_function(numpy.stack(data), axis=0)
            exposures[0].data = stacked_data

        exposure = exposures[0]
        exposure.exptime_n = exptime * stack
        exposure.stack = stack
        exposure.stack_function = stack_function

        if exposure.filename is not None:
            if filename:
                exposure.filename = str(filename)
        else:
            exposure.filename = str(filename or self.image_namer(self, num=num))

        notif_payload = {
            "exptime_total": exposure.exptime_n,
            "image_type": image_type,
            "stack": stack,
        }
        self.notify(CameraEvent.EXPOSURE_DONE, notif_payload)

        if postprocess:
            try:
                exposure = await self._post_process_internal(exposure, **kwargs)
            except ExposureError:
                self.notify(CameraEvent.EXPOSURE_POST_PROCESS_FAILED)
                raise

        if write:
            filename = os.path.realpath(str(exposure.filename))
            self.notify(CameraEvent.EXPOSURE_WRITING, {"filename": filename})

            try:
                await exposure.write()
            except Exception as err:
                raise ExposureError(f"Failed writing image to disk: {err}")

            self.notify(CameraEvent.EXPOSURE_WRITTEN, {"filename": filename})

        return exposure

    @abc.abstractmethod
    async def _expose_internal(self, exposure: Exposure, **kwargs) -> Exposure:
        """Internal method to handle camera exposures.

        This method handles the entire process of exposing and reading the
        camera and return an array or FITS object with the exposed frame.
        If necessary, it must handle the correct operation of the shutter
        before and after the exposure.

        The method receives an `.Exposure` instance in which the exposure
        time, image type, and other parameters have been set by `.expose`.
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
        exposure
            The exposure being taken.
        kwargs
            Other keyword arguments to configure the exposure.
        """

        raise NotImplementedError

    async def _post_process_internal(self, exposure: Exposure, **kwargs) -> Exposure:
        """Performs post-process on an exposure.

        This method can be overridden to perform additional processing on the already
        read exposure. It's called by `.expose` after `._expose_internal` is complete
        but before the image is returned to the user or written to disk.

        The user is responsible for issuing any events. If an `.ExposureError` is
        raised, the error will be propagated and the exposure will not be returned.
        """

        return exposure

    async def disconnect(self) -> bool:
        """Shuts down the camera."""

        try:
            await self._disconnect_internal()
        except CameraConnectionError as ee:
            self.notify(CameraEvent.CAMERA_DISCONNECT_FAILED)
            raise CameraConnectionError(f"failed to disconnect: {ee}")

        self.log("camera has been disconnected.")
        self.notify(CameraEvent.CAMERA_DISCONNECTED)

        return True

    async def _disconnect_internal(self):
        """Internal method to disconnect a camera.

        Must raise a `.CameraConnectionError` if the shutdown fails.
        """

        pass
