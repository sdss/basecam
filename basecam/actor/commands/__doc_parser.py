#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2021-02-16
# @Filename: __doc_parser.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

# This parser is only for documentation purposes and should not be used.

import copy

from . import area, binning, camera_parser, shutter, temperature  # type: ignore


__doc_parser = copy.deepcopy(camera_parser)
__doc_parser.add_command(shutter)
__doc_parser.add_command(temperature)
__doc_parser.add_command(binning)
__doc_parser.add_command(area)
