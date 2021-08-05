#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-12
# @Filename: builtin.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from .card import Card
from .fits import Extension, FITSModel, HeaderModel


__all__ = ["basic_header_model", "basic_fits_model", "basic_fz_fits_model"]

#: A basic header model with camera and exposure information.
basic_header_model = HeaderModel(
    [
        "VCAM",
        "BASECAMV",
        "CAMNAME",
        "CAMUID",
        "IMAGETYP",
        "EXPTIME",
        "EXPTIMEN",
        "STACK",
        "STACKFUN",
        Card(
            "TIMESYS",
            value="TAI",
            comment="The time scale system",
        ),
        Card(
            "DATE-OBS",
            value="{__exposure__.obstime.tai.isot}",
            comment="Date (in TIMESYS) the exposure started",
        ),
    ]
)


#: A basic FITS model for uncompressed images. Includes a single extension
#: with the raw data and a `.basic_header_model`.
basic_fits_model = FITSModel(
    [Extension(data="raw", header_model=basic_header_model, name="PRIMARY")]
)


#: A compressed, basic FITS model. Similar to `.basic_fits_model` but uses
#: ``RICE_1`` compression.
basic_fz_fits_model = FITSModel(
    [
        Extension(
            data="raw",
            header_model=basic_header_model,
            compressed="RICE_1",
            name="PRIMARY",
        )
    ]
)
