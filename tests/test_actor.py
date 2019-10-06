#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-04
# @Filename: test_actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
#
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-10-05 21:12:25

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

    command = actor.issue_command('help')
    await command

    assert len(actor.mock_replies) > 3
