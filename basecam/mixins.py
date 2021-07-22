#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-09
# @Filename: mixins.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import abc
import asyncio

from typing import Callable, Union

from basecam.camera import BaseCamera

from .events import CameraEvent
from .utils import cancel_task


__all__ = ["ShutterMixIn", "ExposureTypeMixIn", "CoolerMixIn", "ImageAreaMixIn"]


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

        return await self._get_shutter_internal()


class ExposureTypeMixIn(object):
    """Methods to take exposures with different image_types."""

    expose: Callable

    async def bias(self, **kwargs):
        """Take a bias image."""

        kwargs.pop("image_type", None)

        return await self.expose(0.0, image_type="bias", **kwargs)

    async def dark(self, exp_time: float, **kwargs):
        """Take a dark image."""

        kwargs.pop("image_type", None)

        return await self.expose(exp_time, image_type="dark", **kwargs)

    async def flat(self, exp_time: float, **kwargs):
        """Take a flat image."""

        kwargs.pop("image_type", None)

        return await self.expose(exp_time, image_type="flat", **kwargs)

    async def object(
        self: Union[BaseCamera, ExposureTypeMixIn],
        exp_time: float,
        **kwargs,
    ):
        """Take a science image."""

        kwargs.pop("image_type", None)

        return await self.expose(exp_time, image_type="object", **kwargs)


class CoolerMixIn(object, metaclass=abc.ABCMeta):
    """Methods to control the cooling system of the camera."""

    _set_temperature_task = None

    notify: Callable

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
            self.notify(CameraEvent.SET_POINT_REACHED, {"temperature": temp})

        # If there is already a set point, cancel it (this does not cancel
        # the cooler changing the temperature).
        await cancel_task(self._set_temperature_task)

        await self._set_temperature_internal(temperature)

        self.notify(CameraEvent.NEW_SET_POINT, {"temperature": temperature})

        loop = asyncio.get_event_loop()
        self._set_temperature_task = loop.create_task(_wait_for_temp(temperature))
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
    async def _get_temperature_internal(self):
        """Internal method to get the camera temperature.

        If the camera can report multiple temperatures, this method must
        return the temperature that the cooler modifies. Other temperature
        can be reported in the status. Must raise `.CameraError` if there is
        a problem.

        """

        raise NotImplementedError


class ImageAreaMixIn(object, metaclass=abc.ABCMeta):
    """Allows to select the image area and binning."""

    async def get_image_area(self):
        """Returns the imaging area as 1-indexed ``(x0, x1, y0, y1)``."""

        return await self._get_image_area_internal()

    @abc.abstractmethod
    async def _get_image_area_internal(self):
        """Internal method to return the image area."""

        raise NotImplementedError

    async def set_image_area(self, area=None):
        """Sets the image area.

        Parameters
        ----------
        area : tuple
            The image area to set as 1-indexed ``(x0, x1, y0, y1)``.
            If not provided, restores the full image area.

        """

        return await self._set_image_area_internal(area=area)

    @abc.abstractmethod
    async def _set_image_area_internal(self, area=None):
        """Internal method to set the image area.

        If ``area=None`` must restore the full image area. In case of error,
        must raise `.CameraError`.

        """

        raise NotImplementedError

    async def get_binning(self):
        """Returns the horizontal and vertical binning as ``(hbin, vbin)``."""

        return await self._get_binning_internal()

    @abc.abstractmethod
    async def _get_binning_internal(self):
        """Internal method to return the binning."""

        raise NotImplementedError

    async def set_binning(self, hbin=1, vbin=None):
        """Sets the binning.

        Parameters
        ----------
        hbin : int
            Horizontal binning.
        vbin : int
            Vertical binning. If not provided, same as ``hbin``.

        """

        assert isinstance(hbin, int), "hbin must be an integer."

        vbin = vbin or hbin
        assert isinstance(vbin, int), "vbin must be an integer."

        return await self._set_binning_internal(hbin, vbin)

    @abc.abstractmethod
    async def _set_binning_internal(self, hbin, vbin):
        """Internal method to set the binning.

        In case of error it must raise `.CameraError`.

        """

        raise NotImplementedError
