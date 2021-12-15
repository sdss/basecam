#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-08-05
# @Filename: utils.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import asyncio
import logging
import os
import pathlib
from contextlib import suppress
from subprocess import CalledProcessError

from sdsstools.logger import SDSSLogger


__all__ = ["LoggerMixIn", "Poller", "cancel_task", "gzip_async", "subprocess_run_async"]


class LoggerMixIn(object):
    """A mixin to provide easy logging with a header."""

    log_header = ""
    logger: SDSSLogger

    def log(self, message, level=logging.DEBUG, use_header=True):
        """Logs a message with a header."""

        header = (self.log_header or "") if use_header else ""

        self.logger.log(level, header + message)


class Poller(object):
    """A task that runs a callback periodically.

    Parameters
    ----------
    name : str
        The name of the poller.
    callback : function or coroutine
        A function or coroutine to call periodically.
    delay : float
        Initial delay between calls to the callback.
    loop : event loop
        The event loop to which to attach the task.

    """

    def __init__(self, name, callback, delay=1, loop=None):

        self.name = name
        self.callback = callback

        self._orig_delay = delay
        self.delay = delay

        self.loop = loop or asyncio.get_event_loop()

        # Create two tasks, one for the sleep timer and another for the poller
        # itself. We do this because we want to be able to cancell the sleep
        # coroutine if we are going to change the delay.
        self._sleep_task = None
        self._task = None

    async def poller(self):
        """The polling loop."""

        while True:

            try:
                if asyncio.iscoroutinefunction(self.callback):
                    await self.callback()
                else:
                    self.callback()
            except Exception as ee:
                self.loop.call_exception_handler(
                    {"message": "failed running callback", "exception": ee}
                )
            self._sleep_task = self.loop.create_task(asyncio.sleep(self.delay))

            await self._sleep_task

    async def set_delay(self, delay=None, immediate=False):
        """Sets the delay for polling.

        Parameters
        ----------
        delay : float
            The delay between calls to the callback. If `None`, restores the
            original delay.
        immediate : bool
            If `True`, stops the currently running task and sets the
            new delay. Otherwise waits for the current task to complete.

        """

        # Only change delay if the difference is significant.
        if delay and abs(self.delay - delay) < 1e-6:
            return

        if not self.running:
            return

        if immediate:
            await self.stop()
            self.start(delay)
        else:
            self.delay = delay or self._orig_delay

    def start(self, delay=None):
        """Starts the poller.

        Parameters
        ----------
        delay : float
            The delay between calls to the callback. If not specified,
            restores the original delay used when the class was instantiated.

        """

        self.delay = delay or self._orig_delay

        if self.running:
            return

        self._task = self.loop.create_task(self.poller())

        return self

    async def stop(self):
        """Cancel the poller."""

        if not self.running:
            return

        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task

    async def call_now(self):
        """Calls the callback immediately."""

        restart = False
        delay = self.delay
        if self.running:
            await self.stop()
            restart = True

        if asyncio.iscoroutinefunction(self.callback):
            await self.loop.create_task(self.callback())
        else:
            self.callback()

        if restart:
            self.start(delay=delay)

    @property
    def running(self):
        """Returns `True` if the poller is running."""

        if self._task and not self._task.cancelled():
            return True

        return False


async def cancel_task(task):
    """Cleanly cancels a task."""

    if task and not task.done():
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def subprocess_run_async(*args, shell=False):
    """Runs a command asynchronously.

    If ``shell=True`` the command will be executed through the shell. In that case
    the argument must be a single string with the full command. Otherwise, must receive
    a list of program arguments. Returns the output of stdout.
    """

    if shell:
        cmd = await asyncio.create_subprocess_shell(
            args[0],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        cmd_str = args[0]

    else:
        cmd = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        cmd_str = " ".join(args)

    stdout, stderr = await cmd.communicate()
    if cmd.returncode and cmd.returncode > 0:
        raise CalledProcessError(
            cmd.returncode,
            cmd=cmd_str,
            output=stdout,
            stderr=stderr,
        )

    if stdout:
        return stdout.decode()


async def gzip_async(file: pathlib.Path | str, complevel=1):
    """Compresses a file with gzip asynchronously."""

    file = str(file)
    if not os.path.exists(file):
        raise FileNotFoundError(f"File not found: {file!r}")

    try:
        await subprocess_run_async(
            "gzip",
            "-" + str(complevel),
            file,
        )
    except Exception as err:
        raise OSError(f"Failed compressing file {file}: {err}")
