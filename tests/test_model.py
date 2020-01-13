#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-12
# @Filename: test_model.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import astropy.io.fits
import astropy.table
import pytest

from basecam import model


class MacroCardTest(model.MacroCard):

    def macro(self, exposure, **kwargs):

        return [('KEYWORD1', 1, 'The first card'),
                ('KEYWORD2', 2)]


def test_fits_model():

    fits_model = model.FITSModel()

    assert len(fits_model) == 1
    assert fits_model[0].data == 'raw'
    assert fits_model[0].header_model is None


def test_fits_model_to_hdu(exposure):

    fits_model = model.FITSModel()

    hdulist = fits_model.to_hdu(exposure)

    assert isinstance(hdulist, astropy.io.fits.HDUList)
    assert isinstance(hdulist[0], astropy.io.fits.PrimaryHDU)
    assert hdulist[0].header is not None
    assert hdulist[0].data is not None


@pytest.mark.parametrize('compressed', [True, 'GZIP_1'])
def test_model_compressed(exposure, compressed):

    fits_model = model.FITSModel([model.Extension(data=None,
                                                  compressed=compressed)])

    exposure.fits_model = fits_model
    hdulist = exposure.to_hdu()

    assert isinstance(hdulist[0], astropy.io.fits.PrimaryHDU)
    assert hdulist[0].data is None

    assert isinstance(hdulist[1], astropy.io.fits.CompImageHDU)
    assert hdulist[1].data is not None


def test_fits_model_multi_extension(exposure):

    fits_model = model.FITSModel([model.Extension(data='none'),
                                  model.Extension(data=None),
                                  model.Extension(data='raw')])

    exposure.fits_model = fits_model
    hdulist = exposure.to_hdu()

    assert len(hdulist) == 3

    assert isinstance(hdulist[0], astropy.io.fits.PrimaryHDU)
    assert hdulist[0].data is None

    assert isinstance(hdulist[1], astropy.io.fits.ImageHDU)
    assert hdulist[1].data is None

    assert isinstance(hdulist[2], astropy.io.fits.ImageHDU)
    assert hdulist[2].data is not None


def test_fits_model_multi_extension_compressed(exposure):

    fits_model = model.FITSModel([model.Extension(data=None, compressed=True),
                                  model.Extension(data=None, compressed=True)])

    exposure.fits_model = fits_model
    hdulist = exposure.to_hdu()

    assert len(hdulist) == 3

    assert isinstance(hdulist[0], astropy.io.fits.PrimaryHDU)
    assert hdulist[0].data is None

    assert isinstance(hdulist[1], astropy.io.fits.CompImageHDU)
    assert hdulist[1].data is not None

    assert isinstance(hdulist[2], astropy.io.fits.CompImageHDU)
    assert hdulist[2].data is None


def test_basic_header_model(exposure):

    basic_header_model = model.models.basic_header_model
    basic_header_model.append(MacroCardTest())

    header = basic_header_model.to_header(exposure)
    assert isinstance(header, astropy.io.fits.Header)
    assert 'IMAGETYP' in header

    description = basic_header_model.describe()
    assert isinstance(description, astropy.table.Table)
    assert len(description) > 0

    assert '### MACRO' in description['name']


def test_macro(exposure):

    macro = MacroCardTest(name='test_macro', use_group_title=False)

    cards = macro.evaluate(exposure)
    assert isinstance(cards, list)

    header = macro.to_header(exposure)
    assert isinstance(header, astropy.io.fits.Header)

    assert len(header) == 2
    assert header.cards['KEYWORD2'].comment == ''


def test_macro_with_group_title(exposure):

    macro = MacroCardTest(name='test_macro', use_group_title=True)
    header = macro.to_header(exposure)

    assert len(header) == 3

    assert header.cards[0].keyword == 'COMMENT'
    assert header.cards[0].value == '######### test_macro #########'


def test_card_group(exposure):

    card_group = model.CardGroup([('KEYW1', 1, 'The first card'),
                                  model.Card(('KEYW2', 2))],
                                 name='card_group')

    assert len(card_group) == 2
    assert isinstance(card_group[0], model.Card)
    assert isinstance(card_group[1], model.Card)

    assert card_group[0].name == 'KEYW1'

    header = card_group.to_header(exposure)
    assert isinstance(header, astropy.io.fits.Header)
    assert len(header) == 3  # Two cards plus the section title


def test_card_group_append(exposure):

    card_group = model.CardGroup([('KEYW1', 1, 'The first card')])
    card_group.append(('KEYW2', 2))

    assert len(card_group) == 2
    assert card_group[1].name == 'KEYW2'


def test_card_group_insert(exposure):

    card_group = model.CardGroup([('KEYW1', 1, 'The first card')])
    card_group.insert(0, ('KEYW2', 2))

    assert len(card_group) == 2
    assert card_group[0].name == 'KEYW2'


def test_evaluate_callable(exposure):

    card = model.Card('testcall', value=lambda x, y: x + y, fargs=(1, 2))

    name, value, comment = card.evaluate(exposure)

    assert name == 'testcall'
    assert comment is None
    assert value == 3
