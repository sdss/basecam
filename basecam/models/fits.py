#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-10
# @Filename: fits.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import functools

import astropy.io.fits
import astropy.table
import numpy

import basecam.exposure

from ..exceptions import CardError
from .card import Card, CardGroup, MacroCard


__all__ = [
    "FITSModel",
    "Extension",
    "HeaderModel",
]

Exposure = basecam.exposure.Exposure


class FITSModel(list):
    """A model representing a FITS image.

    This model defines the data and header for each extension in a FITS
    image. The model can be evaluated for given `.Exposure`, returning a
    fully formed astropy `~astropy.io.fits.HDUList`.

    Parameters
    ----------
    extension
        A list of HDU extensions defined as `.Extension` objects. If none is
        defined, a single, basic extension is added.

    """

    def __init__(self, extensions: list[Extension] = None):

        extensions = extensions or []

        list.__init__(self, extensions)

        if len(self) == 0:
            self.append(Extension(data="raw", name="DATA"))

    def to_hdu(self, exposure: Exposure, context={}):
        """Returns an `~astropy.io.fits.HDUList` from an exposure.

        Parameters
        ----------
        exposure : .Exposure
            The exposure for which the FITS model is evaluated.
        context : dict
            A dictionary of parameters used to fill the card replacement
            fields.

        Returns
        -------
        hdulist : `~astropy.io.fits.HDUList`
            A list of HDUs, each one define by its corresponding `.Extension`
            instance. The first extension is created as a
            `~astropy.io.fits.PrimaryHDU` unless it is compressed, in which
            case an empty primary HDU is prepended.

        """

        hdus = []

        for i, ext in enumerate(self):
            if i == 0:
                primary = True
                if ext.compressed:
                    # Compressed HDU cannot be primary.
                    hdus.append(astropy.io.fits.PrimaryHDU())
            else:
                primary = False
            hdus.append(ext.to_hdu(exposure, primary=primary, context=context))

        return astropy.io.fits.HDUList(hdus)


class Extension(object):
    """A model for a FITS extension.

    Parameters
    ----------
    data : str or numpy.ndarray
        The data for this FITS extension. Can be an array or a macro string
        indicating the type of data to store in the extension. Available macros
        are: ``'raw'`` for the raw image, or ``'none'`` for empty data. If
        `None`, the raw data will only be added to the primary HDU.
    header_model : .HeaderModel
        A `.HeaderModel` for this extension.
    name : str
        The name of the HDU.
    compressed : bool or str
        If `False`, the extension data will not be compressed. Otherwise, a
        string with one of the ``compression_type`` in
        `~astropy.io.fits.CompImageHDU`.

    """

    __VALID_DATA_VALUES = ["raw", "none"]

    def __init__(self, data=None, header_model=None, name=None, compressed=False):

        if isinstance(data, numpy.ndarray):
            self.data = data
        else:
            assert data is None or data in self.__VALID_DATA_VALUES, "invalid data"
            self.data = data

        self.header_model = header_model

        self.name = name
        self.compressed = compressed

    def __repr__(self):

        return f"<Extension (name={self.name!r}, compressed={self.compressed})>"

    def to_hdu(self, exposure, primary=False, context={}):
        """Evaluates the extension as an HDU.

        Parameters
        ----------
        exposure : .Exposure
            The exposure for which we want to evaluate the extension.
        primary : bool
            Whether this is the primary extension.
        context : dict
            A dictionary of arguments used to evaluate the parameters in
            the extension.

        Returns
        -------
        hdu : `~astropy.io.fits.ImageHDU`
            An `~astropy.io.fits.ImageHDU` with the data and header evaluated
            for ``exposure``, or `~astropy.io.fits.CompImageHDU` if
            ``compressed=True``.

        """

        if self.compressed:
            HDUClass = astropy.io.fits.CompImageHDU
            if isinstance(self.compressed, str):
                HDUClass = functools.partial(HDUClass, compression_type=self.compressed)
        else:
            if primary:
                HDUClass = astropy.io.fits.PrimaryHDU
            else:
                HDUClass = astropy.io.fits.ImageHDU

        if not primary:
            HDUClass = functools.partial(HDUClass, name=self.name)

        data = self.get_data(exposure, primary=primary)

        # Create the HDU without a header first to allow astropy to create a
        # basic header (for example, if HDUClass is CompImageHDU this will add
        # the BITPIX keyword). Then append our header.
        hdu = HDUClass(data=data, header=None)

        if self.header_model:
            hdu.header.extend(self.header_model.to_header(exposure, context=context))

        return hdu

    def get_data(self, exposure, primary=False):
        """Returns the data as a numpy array."""

        if isinstance(self.data, str):
            if self.data == "raw":
                data = exposure.data
            else:
                data = None
        elif self.data is None:
            data = exposure.data if primary else None
        else:
            data = self.data

        return data


class HeaderModel(list):
    """A model defining the header of an HDU.

    Parameters
    ----------
    cards : list
        A list of `.Card`, `.CardGroup`, or `MacroCard` instances. Elements
        can also be a tuple of two or three elements (for name, value, and
        optionally a comment).

    Examples
    --------
    >>> header_model = HeaderModel([('TELESCOP', 'APO-2.5', 'The telescope'),
                                    ('OBSERVATORY', 'APO'),
                                    Card('camname', '{(camera).name}')])


    """

    def __init__(self, cards=None):

        cards = [self._process_input(card) for card in cards or []]
        list.__init__(self, cards)

    def __repr__(self):

        return f"<HeaderModel {list.__repr__(self)!s}>"

    def _process_input(self, input_card):
        """Processes the input and converts it into a valid card."""

        if isinstance(input_card, (Card, CardGroup, MacroCard)):
            return input_card
        elif isinstance(input_card, str):
            return Card(input_card)
        else:
            raise CardError(f"invalid input {input_card!r}")

    def append(self, card):
        list.append(self, self._process_input(card))

    def insert(self, idx, card):
        list.insert(self, idx, self._process_input(card))

    def to_header(self, exposure, context={}):
        """Evaluates the header model for an exposure and returns a header.

        Parameters
        ----------
        exposure : .Exposure
            The exposure for which we want to evaluate the model.
        context : dict
            A dictionary of arguments used to evaluate the parameters in
            the model.

        Returns
        -------
        header : `~astropy.io.fits.Header`
            A `~astropy.io.fits.Header`, created by evaluating the model for
            the input exposure.

        """

        header = astropy.io.fits.Header()

        for card in self:

            if isinstance(card, Card):
                header.append(card.evaluate(exposure, context=context))
            elif isinstance(card, (CardGroup, MacroCard)):
                header += card.to_header(exposure, context=context)

        return header

    def describe(self):
        """Returns a table-like representation of the header model."""

        rows = []
        for card in self:
            if isinstance(card, Card):
                rows.append((card.name.upper(), card.value, card.comment))
            elif isinstance(card, CardGroup):
                for card_ in card:
                    rows.append((card_.name.upper(), card_.value, card_.comment))
            elif isinstance(card, MacroCard):
                rows.append(("### MACRO", card.__class__.__name__, ""))
            else:
                raise CardError(
                    f"invalid card {card}. " "This should not have happened."
                )

        return astropy.table.Table(rows=rows, names=["name", "value", "comment"])
