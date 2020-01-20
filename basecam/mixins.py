#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-09
# @Filename: mixins.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import abc
import asyncio

from .events import CameraEvent
from .exceptions import CameraError
from .utils import cancel_task


__all__ = ['ShutterMixIn', 'ExposureTypeMixIn', 'CoolerMixIn']


class ShutterMixIn(object, metaclass=abc.ABCMeta):
    """A mixin that provides manual control over the shutter."""

    @abc.abstractmethod
    async def _set_shutter_internal(self, shutter_open):
        """Internal method to set the position of the shutter."""

        raise NotImplementedError

    @abc.abstractmethod
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


class ExposureTypeMixIn(object):
    """Methods to take exposures with different image_types."""

    async def bias(self, *args, **kwargs):
        """Take a bias image."""

        kwargs.pop('image_type', None)

        return await self.expose(*args, 0.0, image_type='bias', **kwargs)

    async def dark(self, *args, **kwargs):
        """Take a dark image."""

        kwargs.pop('image_type', None)

        return await self.expose(*args, image_type='dark', **kwargs)

    async def flat(self, *args, **kwargs):
        """Take a flat image."""

        kwargs.pop('image_type', None)

        return await self.expose(*args, image_type='flat', **kwargs)

    async def object(self, *args, **kwargs):
        """Take a science image."""

        kwargs.pop('image_type', None)

        return await self.expose(*args, image_type='object', **kwargs)


class CoolerMixIn(object, metaclass=abc.ABCMeta):
    """Methods to control the cooling system of the camera."""

    _set_temperature_task = None

    async def set_temperature(self, temperature):
        """Sets a new temperature goal for the camera.

        Emits a `~.CameraEvent.NEW_SET_POINT` event when the new temperature
        is set. The coroutine blocks until the temperature has been reached
        (at which point it emits `~.CameraEvent.SET_POINT_REACHED`) or until
        the set point changes.

        Parameters
        ----------
        temperature : float
            The goal temperature, in degrees Celsius.

        """

        async def _wait_for_temp(temp):
            while abs(await self.get_temperature() - temp) > 0.1:
                await asyncio.sleep(0.5)
            self._notify(CameraEvent.SET_POINT_REACHED, {'temperature': temp})

        # If there is already a set point, cancel it (this does not cancel
        # the cooler changing the temperature).
        await cancel_task(self._set_temperature_task)

        await self._set_temperature_internal(temperature)

        self._notify(CameraEvent.NEW_SET_POINT, {'temperature': temperature})

        self._set_temperature_task = self.loop.create_task(_wait_for_temp(temperature))
        await self._set_temperature_task

    @abc.abstractmethod
    async def _set_temperature_internal(self, temperature):
        """Internal method to set the camera temperature.

        This method should return immediately after setting the new temperature
        or raise `.CameraError` if there is a problem.

        """

        raise NotImplementedError

    async def get_temperature(self):
        """Returns the temperature of the camera."""

        return await self._get_temperature_internal()

    @abc.abstractmethod
    async def _get_temperature_internal(self, temperature):
        """Internal method to get the cameratemperature.

        If the camera can report multiple temperatures, this method must
        return the temperature that the cooler modifies. Other temperature
        can be reported in the status. Must raise `.CameraError` if there is
        a problem.

        """

        raise NotImplementedError
