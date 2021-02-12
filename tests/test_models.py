#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-12
# @Filename: test_models.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import astropy.io.fits
import astropy.table
import numpy
import pytest

from basecam import models
from basecam.exceptions import CardError, CardWarning
from basecam.models import Card
from basecam.models.card import DefaultCard


class MacroCardTest(models.MacroCard):
    def macro(self, exposure, **kwargs):
        return [("KEYWORD1", 1, "The first card"), ("KEYWORD2", 2)]


def test_fits_model():

    fits_model = models.FITSModel()

    assert len(fits_model) == 1
    assert fits_model[0].data == "raw"
    assert fits_model[0].header_model is None


def test_fits_model_to_hdu(exposure):

    fits_model = models.FITSModel()

    hdulist = fits_model.to_hdu(exposure)

    assert isinstance(hdulist, astropy.io.fits.HDUList)
    assert isinstance(hdulist[0], astropy.io.fits.PrimaryHDU)
    assert hdulist[0].header is not None
    assert hdulist[0].data is not None


@pytest.mark.parametrize("compressed", [True, "GZIP_1"])
def test_model_compressed(exposure, compressed):

    fits_model = models.FITSModel([models.Extension(data=None, compressed=compressed)])

    exposure.fits_model = fits_model
    hdulist = exposure.to_hdu()

    assert isinstance(hdulist[0], astropy.io.fits.PrimaryHDU)
    assert hdulist[0].data is None

    assert isinstance(hdulist[1], astropy.io.fits.CompImageHDU)
    assert hdulist[1].data is not None


def test_fits_model_multi_extension(exposure):

    fits_model = models.FITSModel(
        [
            models.Extension(data="none"),
            models.Extension(data=None),
            models.Extension(data="raw"),
            models.Extension(data=numpy.zeros((10, 10))),
        ]
    )

    exposure.fits_model = fits_model
    hdulist = exposure.to_hdu()

    assert len(hdulist) == 4

    assert isinstance(hdulist[0], astropy.io.fits.PrimaryHDU)
    assert hdulist[0].data is None

    assert isinstance(hdulist[1], astropy.io.fits.ImageHDU)
    assert hdulist[1].data is None

    assert isinstance(hdulist[2], astropy.io.fits.ImageHDU)
    assert hdulist[2].data is not None

    assert isinstance(hdulist[3], astropy.io.fits.ImageHDU)
    assert numpy.all(hdulist[3].data == numpy.zeros((10, 10)))


def test_fits_model_multi_extension_compressed(exposure):

    fits_model = models.FITSModel(
        [
            models.Extension(data=None, compressed=True),
            models.Extension(data=None, compressed=True),
        ]
    )

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

    basic_header_model = models.basic_header_model
    basic_header_model.append(MacroCardTest())
    basic_header_model.append(models.Card("TEST", "test"))

    header = basic_header_model.to_header(exposure)
    assert isinstance(header, astropy.io.fits.Header)
    assert "IMAGETYP" in header
    assert "TEST" in header


def test_header_model_insert(exposure):

    basic_header_model = models.basic_header_model
    basic_header_model.insert(0, Card("A", 1))

    header = basic_header_model.to_header(exposure)
    assert isinstance(header, astropy.io.fits.Header)
    assert header["A"] == 1


def test_header_invalid_card():

    with pytest.raises(CardError):
        basic_header_model = models.basic_header_model
        basic_header_model.insert(0, {})


def test_header_describe(exposure):

    basic_header_model = models.basic_header_model
    basic_header_model.append(MacroCardTest())
    basic_header_model.append(
        models.CardGroup(
            [
                Card("PARAM1", "A parameter"),
                ("PARAM2", "{__camera__.uid}", "Camera UID"),
                Card("VCAM"),
            ]
        )
    )

    description = basic_header_model.describe()
    assert isinstance(description, astropy.table.Table)
    assert len(description) > 0

    assert "### MACRO" in description["name"]
    assert "PARAM2" in description["name"]
    assert description[description["name"] == "PARAM2"]["value"] != ""


def test_macro(exposure):

    macro = MacroCardTest(name="test_macro", use_group_title=False)

    cards = macro.evaluate(exposure)
    assert isinstance(cards, list)

    header = macro.to_header(exposure)
    assert isinstance(header, astropy.io.fits.Header)

    assert len(header) == 2
    assert header.cards["KEYWORD2"].comment == ""


def test_macro_with_group_title(exposure):

    macro = MacroCardTest(name="test_macro", use_group_title=True)
    header = macro.to_header(exposure)

    assert len(header) == 3

    assert header.cards[0].keyword == "COMMENT"
    assert header.cards[0].value == "######### test_macro #########"


def test_card_group(exposure):

    card_group = models.CardGroup(
        [Card("KEYW1", 1, "The first card"), Card("KEYW2", 2)], name="card_group"
    )

    assert len(card_group) == 2
    assert isinstance(card_group[0], models.Card)
    assert isinstance(card_group[1], models.Card)

    assert card_group[0].name == "KEYW1"

    header = card_group.to_header(exposure)
    assert isinstance(header, astropy.io.fits.Header)
    assert len(header) == 3  # Two cards plus the section title


def test_card_group_append(exposure):

    card_group = models.CardGroup([Card("KEYW1", 1, "The first card")])
    card_group.append(Card("KEYW2", 2))

    assert len(card_group) == 2
    assert card_group[1].name == "KEYW2"


def test_card_group_insert(exposure):

    card_group = models.CardGroup([Card("KEYW1", 1, "The first card")])
    card_group.insert(0, Card("KEYW2", 2))

    assert len(card_group) == 2
    assert card_group[0].name == "KEYW2"


def test_evaluate_callable(exposure):

    card = models.Card("testcall", value=lambda x, y: x + y, fargs=(1, 2))

    name, value, comment = card.evaluate(exposure)

    assert name == "testcall"
    assert comment == ""
    assert value == 3


def test_card_evaluate(exposure):

    card = Card("TESTCARD", value="2+2", evaluate=True)
    assert card.evaluate(exposure)[1] == 4


def test_card_default_evaluate(exposure):

    models.DEFAULT_CARDS["TESTCARD"] = models.DefaultCard(
        "TESTCARD",
        value="2+2",
        comment="",
        evaluate=True,
    )

    card = models.Card("TESTCARD")
    assert card.evaluate(exposure)[1] == 4


def test_default_card_overridden():

    card = models.Card("VCAM", value="a value")
    assert card.value == "a value"


def test_card_name_trimming():

    with pytest.warns(CardWarning):
        card = models.Card("AVERYLARGENAME", "value")

    assert card.name == "AVERYLAR"


@pytest.mark.parametrize(
    "value",
    [
        "{the_value}",
        "{__something__.attr}",
        "{__something__}",
    ],
)
def test_card_no_default(exposure, value):
    card = models.Card("MYCARD", value=value)

    with pytest.raises(ValueError) as err:
        assert card.evaluate(exposure=exposure)

    assert "The context does not include all the Card value placeholders" in str(err)


def test_card_default(exposure):
    card = models.Card("MYCARD", value="{some_value_not_passed}", default="a_default")
    result = card.evaluate(exposure=exposure)
    assert result.value == "a_default"


def test_default_card_default_value(exposure):
    del exposure.camera
    card = models.Card("CAMUID")
    assert isinstance(card, DefaultCard)
    assert card.evaluate(exposure).value == "NA"
