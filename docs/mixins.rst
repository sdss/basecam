.. _mixins:

Mixins
======

`.BaseCamera` provides the basic functionality that should be common to any camera: connect, disconnect, and expose. However, most cameras have additional features such as temerature control, binning, etc. ``basecam`` implements some of the more frequent features by the way of :ref:`mixins <api-mixins>`.

A mixin is a class that provides a specific functionality. Classes can be extended with that functionality by subclassing from the mixin. You can think of mixins as building blocks that encapsulate a specific feature.

For example, we can extend our initial camera example with a mixin that allows to read and set the temperature of the CCD ::

    class MyCamera(BaseCamera, CoolerMixIn):

        async def _connect_internal(self, uid):
            self.device = lib.open(uid)

        async def _expose_internal(self, exposure):
            exptime = exposure.exptime
            self._notify(CameraEvent.EXPOSURE_INTEGRATING)
            await self.loop.run_in_executor(None, self.device.expose, exptime)
            self._notify(CameraEvent.EXPOSURE_READING)
            array = await self.loop.run_in_executor(None, self.device.read_frame)
            exposure.data = array
            return

        async def _set_temperature_internal(self, temperature):
            return self.device.set_temp(temperature)

        async def _get_temperature_internal(self):
            return self.device.get_temp('ccd')

With this camera we can now do ::

    >>> await camera.get_temperature():
    25.0
    >>> await camera.set_temperature(-30.)

Note that after subclassing from `.CoolerMixIn` we need to define two new abstract methods: ``_set_temperature_internal`` and ``_get_temperature_internal``. These methods define how to read and set the temperature of the CCD for this specific type of camera, and their implementation will change from camera to camera. The mixin also define two *public methods*: ``set_temperature`` and ``get_temperature``. The public methods provide a uniform way to set and get the temperature from the CCD for all cameras wrapped with ``basecam``.

``basecam`` mixins
------------------

Shutter mixin
^^^^^^^^^^^^^

The `.ShutterMixIn` interfaces with the camera shutter and allows to determine the current position of the shutter or open or close it. When subclassing, the user must override two abstract methods: `._get_shutter_internal` and `._set_shutter_internal`. The position of the shutter is defined as a boolean: `True` for open, `False` for closed. The mixin provides two public methods: `.get_shutter` and `.set_shutter`. ::

    class MyCamera(BaseCamera, ShutterMixIn):
        async def _get_shutter_internal(self):
            pos = self.device.shutter
            if pos == 'O':
                return True
            elif pos == 'C':
                return False

        async def _set_shutter_internal(self, shutter):
            if shutter is True:
                self.device.set_shutter('O')
            else:
                self.device.set_shutter('C')

Exposure type mixin
^^^^^^^^^^^^^^^^^^^

The `.ExposureTypeMixIn` is a helper that adds a series of methods to the camera class that can be used to start an exposure with a specific ``image_type``. The mixin provides: `~.ExposureTypeMixIn.object`, `~.ExposureTypeMixIn.bias`, `~.ExposureTypeMixIn.dark`, and `~.ExposureTypeMixIn.flat`. There is no need to define any abstract method with this mixin. When the camera subclasses from `~.ExposureTypeMixIn` one can do, for example ::

    >>> image = await camera.flat(15.0, stack=3)

This is equivalent to calling ``await camera.expose(15.0, image_type='flat', stack=3)``. Any arguments passed to the mixin methods are forwarded to `~.BaseCamera.expose`.

Cooler mixin
^^^^^^^^^^^^

As we saw earlier, the `.CoolerMixIn` can be used to retrieve the CCD temperature and interface with the cooling system to set the desired set point. The mixin defines two abstract methods: `._get_temperature_internal` which returns the temperature from the camera, and `._set_temperature_internal` which accepts a temperature value and set the camera set point.

The mixin provides to public methods: `.get_temperature` and `.set_temperature`. `.set_temperature` will block asynchronously until the temperature has been reached.

Image area mixin
^^^^^^^^^^^^^^^^

The `.ImageAreaMixIn` allows to set the binning of the image and the area to expose (window). The image area is implemented by the abstract methods `._get_image_area_internal` and `._set_image_area_internal`, with their public counterparts `.get_image_area` and `.set_image_area`. The image area is defined as a 4-element tuple ``(x0, x1, y0, y1)`` where ``x0`` and ``y0`` are the coordinates for the lower left pixel of the window and ``x1`` and ``y1`` the upper right coordinates.

Binning is defined by the abstract methods `._get_binning_internal` (public `.get_binning`) and `._set_binning_internal` (`.set_binning`). The binning is a 2-element tuple with the horizontal and vertical binning.

Generally, cameras that allow to define an image area allow to set binning, and vice-versa, which is why these features are implemented in the same mixin. However. if a camera allows windowing but not binning, one can easily disable that feature ::

    class MyCamera(BaseCamera, ImageAreaMixIn):
        async def _get_binning_internal(self):
            raise NotImplementedError('Binning is not allows in this camera')

        async def _set_binning_internal(self, hbin, vbin):
            raise NotImplementedError('Binning is not allows in this camera')

        async def _get_image_area_internal(self):
            ...

        async def _set_image_area_internal(self, area):
            ...

Creating new mixins
-------------------

Adding new mixins for your particular needs is trivial; just create a new class and define the public and private interfaces. For example, if your camera API allows to reboot it, you can implement a mixin for that feature ::

    class RebootMixIn(object, metaclass=abc.ABCMeta):
        async def reboot(self, delay=0.0):
            """Reboots the camera after a delay."""
            await asyncio.sleep(delay)
            await self._reboot_internal()


        @abc.abstractmethod
        async def _reboot_internal(self):
            raise NotImplementedError()

It is recommended that you set the metaclass to `abc.ABCMeta` and that mark the abstract method with `abc.abstractmethod` since it ensures that ``_reboot_internal`` has been overridden or the program will throw an error when trying to import the class that contains the mixin.
