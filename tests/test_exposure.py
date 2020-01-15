#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-12
# @Filename: test_exposure.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import pytest

from basecam.exceptions import ExposureError


def test_exposure_no_model(exposure):

    exposure.fits_model = None
    hdulist = exposure.to_hdu()

    assert len(hdulist) == 1
    assert hdulist[0].data is not None
    assert 'IMAGETYP' not in hdulist[0].header


def test_exposure_write(exposure, tmp_path):

    test_filename = tmp_path / 'test.fits'
    assert not test_filename.exists()

    exposure.filename = str(test_filename)
    exposure.write()
    assert test_filename.exists()

    test_filename2 = tmp_path / 'test2.fits'
    exposure.write(filename=test_filename2)
    assert test_filename2.exists()


def test_exposure_write_fails(exposure):

    exposure.filename = None

    with pytest.raises(ExposureError):
        exposure.write()


def test_obstime_fails(exposure):

    with pytest.raises(ExposureError):
        exposure.obstime = 12345


def test_obstime_str(exposure):

    test_date = '2019-01-01 00:00:00.000'
    exposure.obstime = test_date

    assert exposure.obstime.utc.iso == test_date