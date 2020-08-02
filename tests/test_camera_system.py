#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-03
# @Filename: test_camera_system.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import asyncio
import logging

import pytest

from .conftest import TEST_CONFIG_FILE, CameraSystemTester, VirtualCamera


pytestmark = pytest.mark.asyncio


async def test_load_config():

    camera_system = CameraSystemTester(VirtualCamera, camera_config=TEST_CONFIG_FILE)

    assert isinstance(camera_system, CameraSystemTester)
    assert 'test_camera' in camera_system._config


async def test_discover(camera_system):

    await camera_system.start_camera_poller(0.1)
    camera_system._connected_cameras = ['DEV_12345']

    await asyncio.sleep(0.2)

    assert len(camera_system.cameras) == 1
    assert isinstance(camera_system.cameras[0], VirtualCamera)

    camera_system._connected_cameras = []

    await asyncio.sleep(0.2)

    assert len(camera_system.cameras) == 0


async def test_camera_connected(camera_system):

    camera_system.on_camera_connected('DEV_12345')

    await asyncio.sleep(0.1)

    assert len(camera_system.cameras) == 1
    assert isinstance(camera_system.cameras[0], VirtualCamera)

    camera_system.on_camera_disconnected('DEV_12345')

    await asyncio.sleep(0.1)

    assert len(camera_system.cameras) == 0


async def test_get_cameras_not_implemented(camera_system, mocker):

    camera_system.list_available_cameras = mocker.Mock(side_effect=NotImplementedError)

    await camera_system.start_camera_poller(0.1)
    await asyncio.sleep(0.5)

    assert camera_system._camera_poller is not None
    assert camera_system._camera_poller.running is False


async def test_config_bad_name(camera_system):

    data = camera_system.get_camera_config('BAD_CAMERA')
    assert data is None


async def test_config_bad_uid(camera_system):

    data = camera_system.get_camera_config(uid='BAD_UID')
    assert data is None


async def test_no_config(camera_system):

    camera_system._config = None

    data = camera_system.get_camera_config('test_camera')
    assert data is None


async def test_config_from_uid(camera_system):

    data = camera_system.get_camera_config(uid='DEV_12345')

    assert data['name'] == 'test_camera'
    assert data['uid'] == 'DEV_12345'


@pytest.mark.parametrize('param,value', [('name', 'test_camera'),
                                         ('uid', 'DEV_12345')])
async def test_add_camerera_already_connected(camera_system, caplog, param, value):

    camera = await eval(f'camera_system.add_camera({param}={value!r})')
    assert camera
    assert getattr(camera, param) == value

    caplog.clear()

    new_camera = await camera_system.add_camera(name='test_camera')

    assert len(caplog.record_tuples) > 0

    last_record = caplog.record_tuples[-1]
    assert last_record[1] == logging.WARNING
    assert 'already connected' in last_record[2]

    assert new_camera == camera


async def test_remove_camera_not_connected(camera_system):

    with pytest.raises(ValueError):
        await camera_system.remove_camera('not_connected_camera')


@pytest.mark.parametrize('params', ['name="test_camera"', 'uid="DEV_12345"',
                                    'name="test_camera", uid="DEV_12345"'])
async def test_get_camera(camera_system, params):

    await camera_system.add_camera(name='test_camera')

    camera = eval(f'camera_system.get_camera({params})')

    assert camera.name == 'test_camera'
    assert camera.uid == 'DEV_12345'


async def test_get_camera_not_found(camera_system):

    camera = camera_system.get_camera('bad_camera')

    assert camera is False


async def test_get_camera_no_params(camera_system):

    await camera_system.add_camera(name='test_camera')
    camera = camera_system.get_camera()

    assert camera


async def test_add_camera_autoconnect(camera_system):

    camera = await camera_system.add_camera(name='test_camera')
    assert camera.connected


async def test_bad_camera_class():

    with pytest.raises(ValueError):
        CameraSystemTester(dict)


async def test_verbose():

    camera_system = CameraSystemTester(VirtualCamera, verbose=True)
    assert camera_system.logger.sh.level == 1

    camera_system = CameraSystemTester(VirtualCamera, verbose=False)
    assert camera_system.logger.sh.level == logging.ERROR


async def test_log_file(tmp_path):

    log_file = tmp_path / 'logfile.log'

    camera_system = CameraSystemTester(VirtualCamera, log_file=log_file)

    assert camera_system.logger.fh is not None

    text = log_file.read_text()
    assert 'logging to ' + str(log_file) in text
