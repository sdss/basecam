#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-10
# @Filename: run_test_actor.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio
import os

from conftest import CameraSystemTester, VirtualCamera

from basecam.actor import CameraActor


CONFIG_FILE = os.path.join(os.path.dirname(__file__), "data/test_config.yaml")


async def main(loop):

    camera_system = CameraSystemTester(VirtualCamera, camera_config=CONFIG_FILE).setup()
    await camera_system.add_camera("test_camera")

    camera_actor = await CameraActor.from_config(CONFIG_FILE, camera_system).start()
    await camera_actor.server.server.serve_forever()


if __name__ == "__main__":

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(loop))
