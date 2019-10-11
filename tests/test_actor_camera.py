#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-04
# @Filename: test_actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio

import pytest


pytestmark = pytest.mark.asyncio


async def test_camera_list(actor):

    await actor.camera_system.add_camera('test_camera')

    command = await actor.invoke_mock_command('camera list')

    await asyncio.sleep(1)

    assert command.is_done
    assert len(actor.mock_replies) == 2
    print(actor.mock_replies)
    assert actor.mock_replies[1]['cameras'] == 'test_camera'
