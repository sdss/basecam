#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-08-06
# @Filename: commands.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)
#
# @Last modified by: José Sánchez-Gallego (gallegoj@uw.edu)
# @Last modified time: 2019-10-04 19:09:10

import clu
from clu import command_parser as basecam_parser


@basecam_parser.command()
async def status(command, camera_system):
    """Reports the status of the camera system."""

    command.set_status(clu.CommandStatus.DONE)
