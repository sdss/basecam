#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-12
# @Filename: test_exposure.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import pytest
from astropy.io.fits import BinTableHDU
from astropy.table import Table

from sdsstools.time import get_sjd

from basecam.exceptions import ExposureError
from basecam.exposure import ImageNamer


def test_exposure_no_model(exposure):

    exposure.fits_model = None
    hdulist = exposure.to_hdu()

    assert len(hdulist) == 1
    assert hdulist[0].data is not None
    assert "IMAGETYP" not in hdulist[0].header


@pytest.mark.asyncio
async def test_exposure_write(exposure, tmp_path):

    test_filename = tmp_path / "test.fits"
    assert not test_filename.exists()

    exposure.filename = str(test_filename)
    await exposure.write()
    assert test_filename.exists()

    test_filename2 = tmp_path / "test2.fits"
    await exposure.write(filename=test_filename2)
    assert test_filename2.exists()


@pytest.mark.asyncio
async def test_exposure_write_fails(exposure):

    exposure.filename = None

    with pytest.raises(ExposureError):
        await exposure.write()


def test_obstime_fails(exposure):

    with pytest.raises(ExposureError):
        exposure.obstime = 12345


def test_obstime_str(exposure):

    test_date = "2019-01-01 00:00:00.000"
    exposure.obstime = test_date

    assert exposure.obstime.utc.iso == test_date


@pytest.mark.parametrize("index", [None, 1])
def test_exposure_extra_hdu(exposure, index):

    extra_hdu = BinTableHDU(Table(rows=[[1, 2, 3]], names=["a", "b", "c"]))
    exposure.add_hdu(extra_hdu, index=index)

    hdulist = exposure.to_hdu()
    assert len(hdulist) == 2

    hdu_index = 1 if index is None else index
    assert isinstance(hdulist[hdu_index], BinTableHDU)


def test_image_namer(tmp_path):

    image_namer = ImageNamer("test_{num:04d}.fits", dirname=tmp_path)

    assert image_namer() == tmp_path / "test_0001.fits"
    assert image_namer._last_num == 1


def test_image_namer_sjd(tmp_path, monkeypatch):

    monkeypatch.setenv("OBSERVATORY", "APO")

    image_namer = ImageNamer("test_{num:04d}.fits", dirname=str(tmp_path) + "/{sjd}")
    sjd = get_sjd("APO")

    assert image_namer() == tmp_path / f"{sjd}/test_0001.fits"
    assert image_namer._last_num == 1


def test_image_namer_overwrite(tmp_path):

    (tmp_path / "test_0001.fits").touch()

    image_namer = ImageNamer("test_{num:04d}.fits", dirname=tmp_path, overwrite=True)

    assert image_namer() == tmp_path / "test_0001.fits"
    assert image_namer._last_num == 1


def test_image_namer_files_exist(tmp_path):

    (tmp_path / "test_0001.fits").touch()
    (tmp_path / "test_0004.fits").touch()

    image_namer = ImageNamer("test_{num:04d}.fits", dirname=tmp_path)

    assert image_namer() == tmp_path / "test_0005.fits"
    assert image_namer._last_num == 5


@pytest.mark.asyncio
async def test_image_name_non_existent_directory(exposure, tmp_path):

    test_filename = tmp_path / "test_dir/another_dir/test.fits"
    assert not test_filename.exists()

    exposure.filename = str(test_filename)
    await exposure.write()
    assert test_filename.exists()


def test_image_namer_files_exist_fz(camera, tmp_path):

    (tmp_path / "test_camera_0001.fits.fz").touch()

    image_namer = ImageNamer("{camera.name}_{num:04d}.fits.fz", dirname=tmp_path)

    assert image_namer(camera=camera) == tmp_path / "test_camera_0002.fits.fz"
    assert image_namer._last_num == 2


def test_image_name_dirname_changes(camera, tmp_path):

    image_namer = ImageNamer(
        "{camera.name}_{num:04d}.fits.fz",
        dirname=tmp_path,
        overwrite=True,
    )

    image_namer._last_num = 5

    assert image_namer(camera=camera) == tmp_path / "test_camera_0006.fits.fz"
    assert image_namer._previous_dirname is not None

    image_namer._previous_dirname = "/home/test"
    assert image_namer(camera=camera) == tmp_path / "test_camera_0001.fits.fz"
