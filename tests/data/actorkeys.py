#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2019-10-10
# @Filename: actorkeys.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

# flake8: noqa


KeysDictionary(
    'camera', (0, 1),
    Key('version', String(help='actor version')),
    Key('text', String(), help='text for humans'),
    Key('cameras', String() * (0,), help='Currently connected cameras'),
    Key('default_cameras', String() * (0,), help='Default cameras'),
    Key('exposure_state',
        String(name='camera', help='name of the camera'),
        Enum('idle','integrating','reading','done','aborted','failed',
             name='state'),
        Float(name='remaining_time',
              help='remaining time for this state (0 if none, short or unknown)',
              units='sec'),
        Float(name='total_time',
              help='total time for this state (0 if none, short or unknown)',
              units='sec'),
        help='Status of current exposure.'),
    Key('filename',
        String(help='last read file'),
        help='last read file'),
    Key('cooler',
        String(name='camera', help='name of the camera'),
        Float(name='set_point', help='CCD temperature setpoint', units='degC'),
        Float(name='ccdTemp',
              help='CCD temperature reported by the camera',
              units='degC'),
        Float(name='heatsink_temp',
              help='Heatsink temperature reported by the camera',
              units='degC'),
        Float(name='cooler_load', help='Load on the cooler', units='percent'),
        Int(name='fanStatus', help='Fan status.'),
        Enum('Off', 'RampingToSetPoint', 'Correcting', 'RampingToAmbient',
             'AtAmbient', 'AtMax', 'AtMin', 'AtSetPoint', 'Invalid',
             name='coolerStatus',
             help='Cooler status.'),
        help='status of camera cooler.'),
    Key('binning',
        String(name='camera', help='name of the camera'),
        Int(name='vertical',help='Binned vertical pixels.',units='pixels'),
        Int(name='horizontal',help='Binned horizontal pixels.',units='pixels'),
        help='How much is the image binned?')

)
