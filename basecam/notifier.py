#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-08-06
# @Filename: notifier.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio
import contextlib
import enum


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
            if not isinstance(self.filter_events, (list, tuple)):
                self.filter_events = [self.filter_events]

            if event not in self.filter_events:
                return False

        for listener in self.listeners:
            listener.put_nowait((event, payload))

        return True


class EventListener(asyncio.Queue):
    """An event queue with callbacks."""

    def __init__(self, loop=None):

        asyncio.Queue.__init__(self)

        self.callbacks = []

        self.loop = loop or asyncio.get_running_loop()

        self.listerner_task = None
        self.listerner_task = self.loop.create_task(self._process_queue())

    async def _process_queue(self):
        """Processes the queue and calls callbacks."""

        while True:
            try:
                event, payload = await self.get()
            except TypeError:
                continue

            for callback in self.callbacks:
                self.loop.create_task(callback(event, payload))

    async def start_listening(self):
        """Starts the listener task. The queue will be initially purged."""

        if self.listerner_task is not None:
            await self.stop_listening()

        # Purges the queue
        while True:
            try:
                self.get_nowait()
            except asyncio.QueueEmpty:
                break

        self.listerner_task = self.loop.create_task(self._process_queue())

    async def stop_listening(self):
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

        assert asyncio.iscoroutinefunction(callback), 'callback must be a coroutine.'

        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def remove_callback(self, callback):
        """De-registers a callback."""

        if callback in self.callbacks:
            self.callbacks.remove(callback)
        else:
            raise ValueError('callback not registered.')
