#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-08-06
# @Filename: notifier.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
#
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-10-03 05:11:26

import asyncio
import contextlib
import enum


class CameraSystemEvent(enum.Enum):
    """Enumeration of camera system events."""

    CAMERA_CONNECTED = enum.auto()
    CAMERA_DISCONNECTED = enum.auto()


class CameraEvent(enum.Enum):
    """Enumeration of camera events."""

    CAMERA_OPEN = enum.auto()
    CAMERA_CLOSED = enum.auto()
    EXPOSURE_STARTED = enum.auto()
    EXPOSURE_FLUSHING = enum.auto()
    EXPOSURE_EXPOSING = enum.auto()
    EXPOSURE_READING = enum.auto()
    EXPOSURE_DONE = enum.auto()
    EXPOSURE_FAILED = enum.auto()


class EventNotifier(object):
    """A registry of clients to be notified of events.

    Allows to register a listener queue in which to announce events.

    Parameters
    ----------
    filter_events : list
        A list of enum values of which to be notified. If `None`,
        all events will be notified.

    """

    def __init__(self, filter_events=None):

        self.listeners = []
        self.filter_events = filter_events

    def register_listener(self, listener):
        """Registers a listener.

        Parameters
        ----------
        listener : .EventListener
            An `.EventListener` instance to which to send events for
            processing.

        """

        assert isinstance(listener, EventListener), 'invalid listener type.'

        if listener not in self.listeners:
            self.listeners.append(listener)

    def remove_listener(self, listener):
        """Removes a listener."""

        if listener not in self.listeners:
            raise ValueError('listener is not registered.')

        self.listeners.remove(listener)

    def notify(self, event, payload={}):
        """Sends an event to all listeners.

        Parameters
        ----------
        event : ~enum.Enum
            An enumeration value belonging to the ``event_class``.
        payload : dict
            A dictionary with the information associated with the event.

        """

        assert isinstance(event, enum.Enum), 'event is not an enum.'

        if self.filter_events is not None:
            if event not in self.filter_events:
                return False

        for listener in self.listeners:
            listener.put_nowait((event, payload))

        return True


class EventListener(asyncio.Queue):
    """An event queue with callbacks."""

    def __init__(self, loop=None):

        self.callbacks = []

        self.loop = loop or asyncio.get_running_loop()

        self.listerner_task = None
        self.loop.create_task(self.start_listener())

    def _process_queue(self):
        """Processes the queue and calls callbacks."""

        while True:
            try:
                event, payload = self.get()
            except TypeError:
                continue

            for callback in self.callbacks:
                self.loop.create_task(callback(event, payload))

    async def start_listener(self):
        """Starts the listener task. The queue will be initially purged."""

        if self.listerner_task is not None:
            await self.stop_listener()

        # Purges the queue
        while True:
            try:
                self.get_nowait()
            except asyncio.QueueEmpty:
                break

        self.listerner_task = self.loop.create_task(self._process_queue())

    async def stop_listener(self):
        """Stops the listener task."""

        if self.listerner_task is None:
            return

        self.listerner_task.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await self.listerner_task

    def register_callback(self, callback):
        """Registers a callback to be called when an event is read.

        Parameters
        ----------
        callback:
            A function or coroutine function to be called. The callback
            receives the event (an enumeration value) as the first argument
            and the payload associated with that event as a dictionary.

        """

        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def remove_callback(self, callback):
        """De-registers a callback."""

        if callback in self.callbacks:
            self.callbacks.remove(callback)
