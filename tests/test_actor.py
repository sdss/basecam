#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-04
# @Filename: test_actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import warnings

import pytest
from clu.misc.logger import ActorHandler


pytestmark = pytest.mark.asyncio


async def test_actor_basic(actor, config):

    actor_config = config['actor']

    assert actor.host == actor_config['host']
    assert actor.port == actor_config['port']

    actor.write(text='test message')
    assert len(actor.mock_replies) > 0
    assert 'text' in actor.mock_replies[0].keywords
    assert actor.mock_replies[0].keywords['text'] == '"test message"'


async def test_logger(actor):

    assert actor.log is not None
    assert len(actor.log.handlers) == 2

    handler_classes = [handler.__class__ for handler in actor.log.handlers]
    assert ActorHandler in handler_classes

    assert len(actor.mock_replies) == 0
    warnings.warn('test warning', UserWarning)
    assert len(actor.mock_replies) == 2


async def test_help(actor):

    command = actor.receive_mock_command('help')
    await command

    assert len(actor.mock_replies) > 3


async def test_arguments_from_config(actor):

    assert actor._config is not None
    assert 'default_cameras' in actor._config

    assert actor.default_cameras == ['test_camera']


async def test_set_default_cameras(actor):

    assert actor.default_cameras == ['test_camera']

    actor.set_default_cameras()
    assert actor.default_cameras is None
