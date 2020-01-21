#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-12
# @Filename: magic.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)


_MAGIC_CARDS = {

    'EXPTIME': ('{__exposure__.exptime}', 'Exposure time of single integration [s]'),
    'EXPTIMEN': ('{__exposure__.exptime_n}', 'Total exposure time [s]'),
    'STACK': ('{__exposure__.stack}', 'Number of stacked frames'),
    'STACKFUN': ('{__exposure__.stack_function}', 'Function used for stacking'),
    'OBSTIME': ('{__exposure__.obstime.tai}', 'Time of the start of the exposure [TAI]'),
    'IMAGETYP': ('{__exposure__.image_type}', 'The image type of the file'),
    'CAMNAME': ('{__camera__.name}', 'Camera name'),
    'CAMUID': ('{__camera__.uid}', 'Camera UID'),
    'VCAM': ('{__camera__.__version__}', 'The version of camera library')

}
