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
        'CAMUID'
        'IMAGETYP',
        'EXPTIME',
        ('TIMESYS', 'TAI', 'All systems at APO operate on the TAI time system'),
        'OBSTIME'
    ]
)


basic_fits_model = FITSModel(
    [Extension(data='raw',
               header_model=basic_header_model,
               name='PRIMARY')]
)
