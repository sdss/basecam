#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-20
# @Filename: test_utils.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio

from basecam.utils import cancel_task


async def test_cancel_task():
    task = asyncio.create_task(asyncio.sleep(3))

    assert await cancel_task(task) is None


async def test_cancel_None():
    assert await cancel_task(None) is None
