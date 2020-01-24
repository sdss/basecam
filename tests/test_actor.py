#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-04
# @Filename: test_actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import pytest
from clu.misc.logger import ActorHandler


pytestmark = pytest.mark.asyncio


async def test_actor_basic(actor, config):

    actor_config = config['actor']

    assert actor.host == actor_config['host']
    assert actor.port == actor_config['port']

    actor.write(text='test message')
    assert len(actor.mock_replies) > 0
    assert 'text' in actor.mock_replies[0]
    assert actor.mock_replies[0]['text'] == 'test message'


async def test_logger(actor):

    assert actor.log is not None
    assert len(actor.log.handlers) == 2
    # It's two because we don't have a file handler for testing.


async def test_help(actor):

    command = actor.invoke_mock_command('help')
    await command

    assert len(actor.mock_replies) == 2
    assert 'help' in actor.mock_replies


async def test_arguments_from_config(actor):

    assert actor._config is not None
    assert 'default_cameras' in actor._config

    assert actor.default_cameras == ['test_camera']


async def test_set_default_cameras(actor):

    assert actor.default_cameras == ['test_camera']

    actor.set_default_cameras()
    assert actor.default_cameras is None

    actor.set_default_cameras('sp1,sp2')
    assert actor.default_cameras == ['sp1', 'sp2']

    actor.set_default_cameras('test_camera')
    assert actor.default_cameras == ['test_camera']

    actor.set_default_cameras(['test_camera'])
    assert actor.default_cameras == ['test_camera']

    with pytest.raises(ValueError):
        actor.set_default_cameras({'bad_input': 1})
