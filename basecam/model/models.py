#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-12
# @Filename: models.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from .base import Extension, FITSModel, HeaderModel


basic_header_model = HeaderModel(
    [
        'VCAM',
        'CAMNAME',
        'CAMUID',
        'IMAGETYP',
        'EXPTIME',
        ('TIMESYS', 'TAI', 'The time scale system'),
        ('DATE-OBS', '{__exposure__.obstime.tai.isot}', 'Date (in TIMESYS) the exposure started')
    ]
)


basic_fits_model = FITSModel(
    [Extension(data='raw',
               header_model=basic_header_model,
               name='PRIMARY')]
)
