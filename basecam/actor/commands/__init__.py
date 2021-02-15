#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2021-02-14
# @Filename: __init__.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from .area import area
from .base import camera_parser, list_
from .binning import binning
from .expose import expose
from .reconnect import reconnect
from .set_default import set_default
from .shutter import shutter
from .status import status
from .temperature import temperature


_MIXIN_TO_COMMANDS = {
    "ShutterMixIn": [shutter],
    "CoolerMixIn": [temperature],
    "ImageAreaMixIn": [binning, area],
}
