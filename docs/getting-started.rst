Getting started
===============

Installation
------------

``basecam`` can be installed by doing ::

    pip install --upgrade sdss-basecam

To install from source, develop, or report an issue, visit ``basecam``'s `GitHub repository <https://github.com/sdss/basecam>`__. ``basecam`` uses `poetry <https://python-poetry.org/>`__ for development.

Basic concepts
--------------

``basecam`` is built around some basic concept that are meant to be general enough that can be applied to any astronomical camera API:

- The **camera system** is in charge of reporting what cameras are connected to the system and provide access to each one of them. It can provide its own system for automatic discovery of new cameras but this is not required. In ``basecam``, the camera system is abstracted by the `.CameraSystem` class.

- A **camera** represents a physical CCD or group of them, along with its cooling mechanisms, shutter, etc. A camera is defined by its **name** and a **unique identifier**, usually the serial number but in general any value that uniquely identifies the camera. Cameras are represented by subclasses of `.BaseCamera`.

- `.BaseCamera` provides an abstract implementation for connecting and disconnecting a camera, retrieving its status, and exposing it. This is expected to be the minimum that all cameras must provide. Additional features (shutter and temperature control, binning) are implemented as :ref:`mixins <mixins>`.

A minimal example
-----------------

Let's assume we have a camera that provides a functional programmatic API. This API can be written in C/C++ or we can use an already existing Python wrapping. We don't care how that API has been implemented or whether is part of the library we are trying to write or external. For now, we'll just assume that we can access the functions of that library through the module ``lib``.

To wrap the camera API with ``basecam`` we need to subclass `.CameraSystem` and `.BaseCamera` and override the internal :ref:`abstract methods <abstract-methods>` to connect it to the camera low-level implementation.

.. code-block:: python

    # file: camera.py

    import lib

    from basecam import CameraSystem, BaseCamera, CameraEvent


    class MyCameraSystem(CameraSystem):

        __version__ = '0.0.1'

        def list_available_cameras(self):
            return lib.cameras


    class MyCamera(BaseCamera):

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


That's it! Of course, a real camera implementation can be a bit more complicated, but this is all we minimally need to do. Now we can control the cameras using ``basecam``'s API ::

    >>> camera_system = MyCameraSystem(MyCamera)
    >>> camera = await camera_system.add_camera(name='my_camera', uid='S12345', autoconnect=True)
    >>> camera.connected
    True
    >>> camera.name, camera.uid
    ('my_camera', 'S12345')
    >>> exposure = await camera.expose(1)
    >>> exposure.write()
    >>> exposure.filename
    'S12345-0001.fits'

Note that when we instantiate ``MyCameraSystem`` we pass it the class we want to use for it to connect new cameras, in this case ``MyCamera``. The rest is pretty straightforward.

Normally we instantiate the camera system with a configuration dictionary or file that includes information about the available cameras and how to connect them. For example, imagine that to connect the camera we need to know the device port in addition to the unique identifier ::

    def _connect_internal(self, uid, port):
        self.device = lib.open(uid, port)

We can instantiate ``MyCameraSystem`` as follows ::

    >>> config = {
            'cameras': {
                'my_camera': {
                    'uid': 'S12345'
                    'connection_params': {
                        'uid': 'S12345'
                        'port': '/dev/cam1'
                    }
                }
            }
        }
    >>> camera_system = MyCameraSystem(MyCamera, camera_config=config)

Now we can use the camera poller to automatically detect when cameras connect or disconnect ::

    >>> await camera_system.start_camera_poller()

`~.CameraSystem.start_camera_poller` periodically checks the list of available cameras; when a new camera is connected, it calls `~.CameraSystem.add_camera`. The configuration for the camera is accessible via ``BaseCamera.camera_config`` and the ``connection_params`` section is passed to `~.BaseCamera._connect_internal`.

Note that when interacting with the camera system or the camera we do not use the internal methods we have overridden. To expose the camera, we call `~.BaseCamera.expose` which provides a common interface regardless of the specific camera. `~.BaseCamera.expose` returns an `.Exposure` object which contains the image and a `FITS model <.FITSModel>`. More details are provided in the :ref:`exposure` section.

A more complete example
-----------------------

For a more complete example of a full implementation of a camera API with ``basecam`` we refer the reader to `flicamera <https://github.com/sdss/flicamera>`__. ``flicamera`` provides a full wrapping of `Finger Lakes Instrumentation <http://www.flicamera.com/>`__ cameras as part of the SDSS-V project. The structure of the project is quite simple and can be summarised as follows ::

    flicamera
     |
     -- actor.py
     |
     -- camera.py
     |
     -- lib.py

In `lib.py <https://github.com/sdss/flicamera/blob/master/flicamera/lib.py>`__ we wrap the vendor C library using `ctypes`. This is a typical approach but we could have also used `Cython <https://cython.readthedocs.io/en/latest/index.html>`__ or `pybind11 <https://pybind11.readthedocs.io/en/stable>`__, or an already existing Python implementation such as `python-FLI <https://github.com/cversek/python-FLI>`__. This exposes the low-level functions we need to wrap using ``basecam``.

`camera.py <https://github.com/sdss/flicamera/blob/master/flicamera/camera.py>`__ includes the subclasses of `.CameraSystem` and `.BaseCamera` that implement ``basecam``'s API for the FLI cameras. Note that, although more complicated than the example above, the whole file has fewer than 200 lines.

Finally `actor.py <https://github.com/sdss/flicamera/blob/master/flicamera/actor.py>`__ provides the implementation of the camera :ref:`actor <actor>`.

General recommendations
-----------------------

``basecam`` is an asynchronous library so you'll need a basic understanding of how `asyncio` works. That said, most of the wrapping code can be written synchronously. An exception, as seen in the example above, is calling long-running blocking routines from the camera library. A typical example is the function that reads the camera buffer, which in some case may take up to several seconds. In that case you want to run that code in an `executor <asyncio.loop.run_in_executor>` ::

    await self.loop.run_in_executor(None, lib.grab_frame)

Note that you can access the event loop from ``CameraSystem.loop`` or ``BaseCamera.loop``.

As a general rule, when wrapping the camera library, you want to minimally provide access to the features in the camera API but avoiding any additional implementation: leave that to ``basecam``. The implementation of the :ref:`abstract methods <abstract-methods>` and :ref:`mixins <mixins>` must also be as minimal as possible, with each method doing only what is required.
