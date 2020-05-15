.. _abstract-methods:

Abstract methods
================

``basecam`` relies on the concept of `abstract classes <https://docs.python.org/3/library/abc.html>`__: classes that cannot be instantiated unless they are subclassed and a series of methods and properties have been overridden and implemented. `.CameraSystem`, `.BaseCamera`, and the :ref:`mixins <mixins>` are defined as `abc` abstract classes. The process of wrapping a new camera entails to subclass these base classes and override the necessary methods with the concrete implementation for the camera. In addition, some methods such as `.CameraSystem.setup` are not abstract methods but may need to be overridden depending on the camera implementation.

In this section we describe each on of the existing abstract methods (mandatory and optional) and provide details about how they must be implemented. The abstract methods for mixins are described in :ref:`their own section <mixins>`.


CameraSystem
------------

For `.CameraSystem` the only required abstract method is `~.CameraSystem.list_available_cameras`. This method must be overridden to return a list or tuple of the unique identifiers that the native camera system detects are connected. For example ::

    def list_available_cameras(self):

        devices_id = self.lib.list_cameras()

        # Get the serial number as UID.
        serial_numbers = []
        for device_id in devices_id:
            device = flicamera.lib.FLIDevice(device_id, self.lib.libc)
            serial_numbers.append(device.serial)

        return serial_numbers

This method can be called manually and it is also used by the camera poller to determine whether new cameras have been connected/disconnected and call `.add_camera` or `.remove_camera` automatically.

Some camera libraries need to be initialised in a particular way, or you may want to set some attributes. For that, you can override `.CameraSystem.setup` ::

    def setup(self):

        self.lib = flicamera.lib.LibFLI()

        return self

Note that this method *must* return ``self``. This is so that the camera system can conveniently be instantiated and setup as ::

    camera_system = CameraSystem(CameraClass).setup()

If `~.CameraSystem.setup` is not overridden, it does nothing.

Finally, you'll also need to override the ``__version__`` property, which must return the version of the camera system. The easiest way of doing this is ::

    class MyCameraSystem(CameraSystem):

        __version__ = '0.0.1'


BaseCamera
----------

`.BaseCamera` must implement all the minimal features to control the camera. This includes connecting and disconnecting it, retrieving its status and unique identifier, and exposing and reading the camera. The camera system and camra configuration passed by `.add_camera` can be accessed from the ``camera_system`` and ``camera_config`` attributes, respectively.

`async def _connect_internal <._connect_internal>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Opens the camera and makes sure it's ready to be accessed. It must raise a `.CameraConnectionError` if the connection fails. The signature of the method must include any keyword parameter that is needed to connect the camera, which must be the same as the parameters in the ``connection_params`` section in the :ref:`camera configuration <configuration>`. ::

    async def _connect_internal(self, serial=None):

        if not serial:
            raise basecam.exceptions.CameraConnectionError('unknown serial number.')

        self._device = self.camera_system.lib.get_camera(serial)

        if self._device is None:
            raise basecam.exceptions.CameraConnectionError(
                f'cannot find camera with serial {serial}.')

        return self

`._connect_internal` is called by the public method `.connect`, which takes care of passing the necessary arguments, notifying the :ref:`listeners <events>` of the `~.CameraEvent.CAMERA_CONNECTED` or `.CAMERA_CONNECT_FAILED` events. If the connection is successful, `.connect` will set ``BaseCamera.connected=True``.

`def _uid_internal <._uid_internal>` (optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This property is the internal counterpart of `~.uid`. It must return the camera unique identifier (UID; this can be any string, integer, or other type that is used to identify the camera). If not overridden it returns `None`. In this case, `~.uid` will try to retrieve the UID from the camera configuration. If that is not available; the camera will fail during the connection stage. ::

    @property
    def _uid_internal(self):

        return self._device.serial

`def _status_internal <._status_internal>` (optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Called by `.get_status`. Must returns a dictionary of all the relevant status parameters the camera is aware of (temperature, firmware version, serial, binning, etc.) By default, it returns an empty dictionary. ::

    def _status_internal(self):

        device = self._device
        device._update_temperature()

        return dict(model=device.model,
                    serial=device.serial,
                    fwrev=device.fwrev,
                    hwrev=device.hwrev,
                    hbin=device.hbin,
                    vbin=device.vbin,
                    visible_area=device.get_visible_area(),
                    image_area=device.area,
                    temperature_ccd=device._temperature['CCD'],
                    temperature_base=device._temperature['base'],
                    exposure_time_left=device.get_exposure_time_left(),
                    cooler_power=device.get_cooler_power())

`async def _expose_internal <._expose_internal>`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Called by `.expose`. This method must implement the exposing and reading of a camera frame. The method receives an `.Exposure` instance for the frame which contains the type of image to take and the exposure time. After taking and reading the exposure, it must set ``exposure.data`` with a numpy array of the data just read. It must raise an `.ExposureError` if something goes wrong. An example of implementation, taken from `flicamera <https://github.com/sdss/flicamera/blob/master/flicamera/lib.py>`__ ::

    async def _expose_internal(self, exposure, **kwargs):

        TIMEOUT = 5

        device = self._device

        device.cancel_exposure()

        device.set_exposure_time(exposure.exptime)

        image_type = exposure.image_type
        frametype = 'dark' if image_type in ['dark', 'bias'] else 'normal'
        device.start_exposure(frametype)

        exposure.obstime = astropy.time.Time.now()
        self._notify(CameraEvent.EXPOSURE_INTEGRATING)

        start_time = time.time()
        time_left = exposure.exptime

        while True:

            await asyncio.sleep(time_left)

            time_left = device.get_exposure_time_left() / 1000.

            if time_left == 0:
                self._notify(CameraEvent.EXPOSURE_READING)
                array = await self.loop.run_in_executor(None, device.read_frame)
                exposure.data = array
                return

            if time.time() - start_time > exposure.exptime + TIMEOUT:
                raise ExposureError('timeout waiting for exposure to finish.')

There are a few  things to note here. Because some cameras may not differentiate between the process of integrating and reading, `._expose_internal` must take care of both. That means that the method is responsible from emitting notifications of when integration and reading starts by calling `._notify` with the appropriate `.CameraEvent`. Other exposure events are handled by `.expose`.

Long running processes such as integration (if it's not asynchronous) and reading must be run in an `executor <asyncio.loop.run_in_executor>` to avoid them blocking the loop (which can be accessed as ``self.loop``. You can use the executor in any way you want, whether it is using the default executor or any subclass of `concurrent.futures.Executor`.

`.expose` sets ``Exposure.obstime`` just before calling `._expose_internal`. However, if you want additional precision on when the exposure exactly started, you can set the value again, which must be and `astropy.time.Time` object.

Note that you don't need to care about stacking or saving the image; that's all taken care in `.expose` (the public interface is described in :ref:`exposing`). However, `._expose_internal` must take care of operating the shutter if this is not done automatically by the API when exposing. For this two attributes, ``has_shutter`` and ``auto_shutter``, can be set when subclassing `.BaseCamera` to indicate whether the camera has a shutter and if this opens and closes automatically when an exposure is commanded ::

    class MyCamera(BaseCamera):

        has_shutter = True
        auto_shutter = False

These parameters can also be set in the configuration file ::

    cameras: {
        my_camera: {
            has_shutter: true
            auto_shutter: false
        }
    }

`async def _disconnect_internal <._disconnect_internal>` (optional)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Called by `~.BaseCamera.disconnect`. By default does nothing but can be overridden to close the camera. Must raise a `.CameraConnectionError` if a problem is found.


Summary of abstract methods
---------------------------

.. list-table::
   :widths: 20 20 30 40 100
   :header-rows: 1

   * - Class
     - Name
     - Type
     - Optional
     - Purpose
   * - `.CameraSystem`
     - `~.CameraSystem.list_available_cameras`
     - method
     - No
     - Return list of unique identifiers of system cameras.
   * -
     - `~.CameraSystem.setup`
     - method
     - Yes
     - Setup the camera system. Must return ``self``.
   * -
     - ``__version__``
     - property
     - No
     - Return the version of the camera system.
   * - `.BaseCamera`
     - `~.BaseCamera._connect_internal`
     - async method
     - No
     - Establish connection with the camera and make it ready.
   * -
     - `~.BaseCamera._uid_internal`
     - property
     - Yes
     - Return the unique identifier of the camera. By default, returns `None`.
   * -
     - `~.BaseCamera._status_internal`
     - method
     - Yes
     - Return a dictionary with status parameters.
   * -
     - `~.BaseCamera._expose_internal`
     - async method
     - No
     - Expose and read the camera and populate `Exposure.data <.Exposure>`. Must notify of integrating and reading stages.
   * -
     - `~.BaseCamera._disconnect_internal`
     - async method
     - Yes
     - Disconnect the camera.
