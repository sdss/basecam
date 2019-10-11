#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-10
# @Filename: actorkeys.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

KeysDictionary(
    'camera', (0, 1),
    Key('version', String(help='actor version')),
    Key('text', String(), help='text for humans'),
    Key('cameras', String() * (0,), help='Currently connected cameras')
)
