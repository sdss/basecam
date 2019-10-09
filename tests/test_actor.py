#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-04
# @Filename: test_actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import pytest


pytestmark = pytest.mark.asyncio


async def test_actor_basic(actor, config):

    actor_config = config['actor']

    assert actor.host == actor_config['host']
    assert actor.port == actor_config['port']

    actor.write(text='test message')
    assert len(actor.mock_replies) > 0
    assert 'text' in actor.mock_replies[0].keywords
    assert actor.mock_replies[0].keywords['text'] == '"test message"'


async def test_help(actor):

    command = actor.receive_mock_command('help')
    await command

    assert len(actor.mock_replies) > 3


async def test_arguments_from_config(actor):

    assert actor._config is not None
    assert 'default_cameras' in actor._config

    assert actor.default_cameras == ['test_camera']
