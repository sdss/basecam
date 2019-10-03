#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-08-05
# @Filename: helpers.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
#
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-10-03 05:01:00

import asyncio
import logging
from contextlib import suppress

import astropy.time
import astropy.io.fits

from .utils import get_logger


class LoggerMixIn(object):
    """A mixin to provide easy logging with a header.

    Parameters
    ----------
    name : str
        The name of the logger to which to output.
    log_header : str
        A header to prefix to each message.

    """

    def __init__(self, name, log_header=None):

        self.logger = get_logger(name)
        self.log_header = log_header

    def log(self, message, level=logging.DEBUG, use_header=True):
        """Logs a message with a header."""

        header = (self.log_header or '') if use_header else ''

        self.logger.log(level, header + message)


class Poller(object):
    """A task that runs a callback periodically.

    Parameters
    ----------
    callback : function or coroutine
        A function or coroutine to call periodically.
    delay : float
        Initial delay between calls to the callback.
    loop : event loop
        The event loop to which to attach the task.

    """

    def __init__(self, callback, delay=1, loop=None):

        self.callback = callback

        self._orig_delay = delay
        self.delay = delay

        self.loop = loop or asyncio.get_running_loop()

        # Create two tasks, one for the sleep timer and another for the poller
        # itself. We do this because we want to be able to cancell the sleep
        # coroutine if we are going to change the delay.
        self._sleep_task = None
        self._task = None

    async def poller(self):
        """The polling loop."""

        while True:

            if asyncio.iscoroutinefunction(self.callback):
                await asyncio.create_task(self.callback())
            else:
                self.callback()

            self._sleep_task = asyncio.create_task(asyncio.sleep(self.delay))

            await self._sleep_task

    async def set_delay(self, delay=None):
        """Sets the delay for polling.

        Parameters
        ----------
        delay : float
            The delay between calls to the callback. If `None`, restores the
            original delay."""

        await self.stop()
        self.start(delay)

    def start(self, delay=None):
        """Starts the poller.

        Parameters
        ----------
        delay : float
            The delay between calls to the callback. If not specified,
            restores the original delay used when the class was instantiated.

        """

        if self.running:
            raise RuntimeError('poller is already running.')

        self.delay = delay or self._orig_delay
        self._task = asyncio.create_task(self.poller())

        return self

    async def stop(self):
        """Cancel the poller."""

        if not self.running:
            return

        self._task.cancel()

        with suppress(asyncio.CancelledError):
            await self._task

    @property
    def running(self):
        """Returns `True` if the poller is running."""

        if self._task and not self._task.cancelled():
            return True

        return False


def create_fits_image(data, exptime, obstime=None, **extra):
    """Creates a FITS object from an image, with associated header.

    This function is mostly intended to be called by
    `~.Camera._expose_internal` to wrap the exposed image.

    Parameters
    ----------
    data : ~numpy.array
        The array with the image data.
    exptime : float
        The exposure time, in seconds.
    obstime : ~astropy.time.Time
        A `~astropy.time.Time` object with the time of the observation. If
        not provided, uses the current time minus the exposure time.
    extra : ~astropy.io.fits.Header or dict
        A sequence of keyword-value pair to add to the header.

    Returns
    -------
    fits : `~astropy.io.fits.HDUList`
        An HDU list with a single extension containing the image data
        and header.

    """

    if not obstime:
        obstime = astropy.time.Time.now() - astropy.time.TimeDelta(exptime, format='sec')

    header = astropy.io.fits.Header(
        [
            ('DATE-OBS', obstime.isot, 'Date at start of integration'),
            ('TIMESYS', obstime.scale.upper(), 'Time Zone of Date'),
            ('EXPTIME', exptime, 'Exposure time [s]')
        ]
    )

    header.update(extra)

    hdu = astropy.io.fits.PrimaryHDU(data=data, header=header)
    hdul = astropy.io.fits.HDUList([hdu])

    return hdul
