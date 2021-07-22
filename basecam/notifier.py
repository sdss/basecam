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


__all__ = ["EventNotifier", "EventListener"]


class EventNotifier(object):
    """A registry of clients to be notified of events.

    Allows to register a listener queue in which to announce events.

    """

    def __init__(self):

        self.listeners = []

    def register_listener(self, listener):
        """Registers a listener.

        Parameters
        ----------
        listener : .EventListener
            An `.EventListener` instance to which to send events for
            processing.

        """

        assert isinstance(listener, EventListener), "invalid listener type."

        if listener not in self.listeners:
            self.listeners.append(listener)

    def remove_listener(self, listener):
        """Removes a listener."""

        if listener not in self.listeners:
            raise ValueError("listener is not registered.")

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

        assert isinstance(event, enum.Enum), "event is not an enum."

        for listener in self.listeners:

            if listener.filter_events and event not in listener.filter_events:
                return False

            listener.put_nowait((event, payload))

        return True


class EventListener(asyncio.Queue):
    """An event queue with callbacks.

    Parameters
    ----------
    filter_events : list
        A list of enum values of which to be notified. If `None`,
        all events will be notified.
    autostart : bool
        Whether to start the listener as soon as the object is created.

    """

    def __init__(self, loop=None, filter_events=None, autostart=True):

        asyncio.Queue.__init__(self)

        self.callbacks = []

        self.loop = loop or asyncio.get_running_loop()

        self.filter_events = filter_events
        if self.filter_events and not isinstance(self.filter_events, (list, tuple)):
            self.filter_events = [self.filter_events]

        self.listerner_task = None

        self._event_waiter = None
        self.__events = set()  # A list of events received to be used by wait_for

        if autostart:
            self.listerner_task = self.loop.create_task(self._process_queue())

    async def _process_queue(self):
        """Processes the queue and calls callbacks."""

        while True:
            try:
                event, payload = await self.get()
            except TypeError:
                continue

            for callback in self.callbacks:
                cb = callback(event, payload)
                if asyncio.iscoroutine(cb):
                    self.loop.create_task(cb)

            if self._event_waiter:
                self.__events.add(event)
                self._event_waiter.set()

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
            If the callback is a coroutine, it is scheduled as a task.

        """

        if callback not in self.callbacks:
            self.callbacks.append(callback)

    def remove_callback(self, callback):
        """De-registers a callback."""

        if callback in self.callbacks:
            self.callbacks.remove(callback)
        else:
            raise ValueError("callback not registered.")

    async def wait_for(self, events, timeout=None):
        """Blocks until a certain event happens.

        Parameters
        ----------
        events
            The event to wait for. It can be a list of events, in which case
            it returns when any of the events has been seen.
        timeout : float or None
            Timeout in seconds. If `None`, blocks until the event is received.

        Returns
        -------
        result : bool
            Returns a `set` of events received that intersects with the
            ``events`` that were being waited for. Normally this is a single
            event, the first one to be seen, but it can be more than one if
            multiple events that were being waited for happen at the same time.
            Returns `False` if the routine timed out before receiving the event.

        """

        # We need __events to be a list because if two events arrive too close
        # we may miss some of them.
        self._event_waiter = asyncio.Event()
        self.__events = set()

        events = set(events) if isinstance(events, (list, tuple)) else set([events])

        async def _waiter():
            assert self._event_waiter
            while not events.intersection(self.__events):
                await self._event_waiter.wait()
                # Clear the event waiter. If __last_event == event
                # then it doesn't matter. If _last_event != event,
                # this will block in the next loop.
                self._event_waiter.clear()
            return True

        try:
            await asyncio.wait_for(_waiter(), timeout)
            event_inters = events.intersection(self.__events)
            return event_inters
        except asyncio.TimeoutError:
            return False
        finally:
            self._event_waiter.set()
            self._event_waiter = None
            self.__events = set()
