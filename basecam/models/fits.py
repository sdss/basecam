#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-10
# @Filename: fits.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import functools
from copy import copy

from typing import Any, Dict, List, Optional, TypeVar, Union

import astropy.io.fits
import astropy.table
import numpy

import basecam.exposure

from ..exceptions import CardError
from .card import DEFAULT_CARDS, Card, CardGroup, MacroCard


try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal


__all__ = [
    "FITSModel",
    "Extension",
    "HeaderModel",
]


Exposure = basecam.exposure.Exposure

ImageHDUType = Union[
    astropy.io.fits.ImageHDU,
    astropy.io.fits.CompImageHDU,
    astropy.io.fits.PrimaryHDU,
]
_CardTypes = Union[Card, CardGroup, MacroCard, str, tuple, list, None]
T = TypeVar("T", bound="FITSModel")


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
    context
        A default context to pass to the header model when evaluating it.
    """

    def __init__(
        self,
        extensions: Optional[List[Extension]] = None,
        context: Dict[str, Any] = {},
    ):

        self.context: Dict[str, Any] = context

        extensions = extensions or []
        list.__init__(self, extensions)

        if len(self) == 0:
            self.append(Extension(data="raw", name="DATA"))

    def copy(self: T) -> T:
        return copy(self)

    def to_hdu(
        self,
        exposure: Exposure,
        context: Dict[str, Any] = {},
    ) -> astropy.io.fits.HDUList:
        """Returns an `~astropy.io.fits.HDUList` from an exposure.

        Parameters
        ----------
        exposure
            The exposure for which the FITS model is evaluated.
        context
            A dictionary of parameters used to fill the card replacement
            fields. Updates the default context.

        Returns
        -------
        hdulist
            A list of HDUs, each one define by its corresponding `.Extension`
            instance. The first extension is created as a
            `~astropy.io.fits.PrimaryHDU` unless it is compressed, in which
            case an empty primary HDU is prepended.
        """

        hdus = []

        ucontext = self.context.copy()
        ucontext.update(context)

        for i, ext in enumerate(self):
            if i == 0:
                primary = True
                if ext.compressed:
                    # Compressed HDU cannot be primary.
                    hdus.append(astropy.io.fits.PrimaryHDU())
                    primary = False
            else:
                primary = False
            hdus.append(ext.to_hdu(exposure, primary=primary, context=ucontext))

        return astropy.io.fits.HDUList(hdus)


class Extension(object):
    """A model for a FITS extension.

    Parameters
    ----------
    data
        The data for this FITS extension. Can be an array or a macro string
        indicating the type of data to store in the extension. Available macros
        are: ``'raw'`` or `None` for the raw image, or ``'none'`` for empty data.
    header_model
        A `.HeaderModel` for this extension.
    name
        The name of the HDU.
    compressed
        If `False`, the extension data will not be compressed. Otherwise, a
        string with one of the ``compression_type`` in
        `~astropy.io.fits.CompImageHDU`.
    compression_params
        Additional parameters to be passed to `~astropy.io.fits.CompImageHDU` if the
        extension is compressed.
    """

    __VALID_DATA_VALUES = ["raw", "none", True, False]

    def __init__(
        self,
        data: Union[Literal["raw"], Literal["none"], None, bool, numpy.ndarray] = None,
        header_model: Optional[HeaderModel] = None,
        name: Optional[str] = None,
        compressed: Union[bool, str] = False,
        compression_params: dict[str, Any] = {},
    ):

        if isinstance(data, numpy.ndarray):
            self.data = data
        else:
            assert data is None or data in self.__VALID_DATA_VALUES, "invalid data"
            self.data = data

        self.header_model = header_model

        self.name = name

        self.compressed = compressed
        if self.compressed is True:
            self.compressed = "GZIP_2"
        self._compression_params = compression_params

    def __repr__(self):
        return f"<Extension (name={self.name!r}, compressed={self.compressed})>"

    def to_hdu(
        self,
        exposure: Exposure,
        primary: bool = False,
        context: Dict[str, Any] = {},
    ) -> ImageHDUType:
        """Evaluates the extension as an HDU.

        Parameters
        ----------
        exposure
            The exposure for which we want to evaluate the extension.
        primary
            Whether this is the primary extension.
        context
            A dictionary of arguments used to evaluate the parameters in
            the extension.

        Returns
        -------
        hdu
            An `~astropy.io.fits.ImageHDU` with the data and header evaluated
            for ``exposure``, or `~astropy.io.fits.CompImageHDU` if
            ``compressed=True``.
        """

        if self.compressed:
            HDUClass = astropy.io.fits.CompImageHDU
            if isinstance(self.compressed, str):
                HDUClass = functools.partial(
                    HDUClass,
                    compression_type=self.compressed,
                    **self._compression_params,
                )
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

    def get_data(
        self,
        exposure: Exposure,
        primary: bool = False,
    ) -> Union[numpy.ndarray, None]:
        """Returns the data as a numpy array."""

        if isinstance(self.data, str):
            if self.data == "raw":
                data = exposure.data
            else:
                data = None
        elif isinstance(self.data, numpy.ndarray):
            data = self.data
        elif self.data is None or self.data is True:
            data = exposure.data
        elif self.data is False:
            data = None
        else:
            raise ValueError(f"Invalid data value {self.data!r}")

        return data


class HeaderModel(list):
    """A model defining the header of an HDU.

    Parameters
    ----------
    cards
        A list of `.Card`, `.CardGroup`, or `MacroCard` instances. It can also be a
        string with the name of a :ref:`default card <default-cards>`.

    Examples
    --------
    >>> header_model = HeaderModel([Card('TELESCOP', 'APO-2.5', 'The telescope'),
                                    Card('OBSERVATORY', 'APO'),
                                    'EXPTIME',
                                    Card('camname', '{(camera).name}')])
    """

    def __init__(self, cards: List[_CardTypes] = []):

        cards = [self._process_input(card) for card in cards]
        list.__init__(self, cards)

    def __repr__(self):

        return f"<HeaderModel {list.__repr__(self)!s}>"

    def _process_input(self, input_card: _CardTypes) -> _CardTypes:
        """Processes the input and converts it into a valid card."""

        if isinstance(input_card, (Card, CardGroup, MacroCard)):
            return input_card
        elif isinstance(input_card, str):
            if input_card not in DEFAULT_CARDS:
                raise CardError(f"{input_card} is not a default card.")
            return Card(input_card.upper())
        elif isinstance(input_card, (tuple, list)):
            name, value, *other = input_card
            return Card(name, value=value, comment=other[0] if other else "")
        elif input_card is None:
            return None
        else:
            raise CardError(f"invalid input {input_card!r}")

    def append(self, card: _CardTypes):
        list.append(self, self._process_input(card))

    def insert(self, idx: int, card: _CardTypes):
        list.insert(self, idx, self._process_input(card))

    def to_header(
        self,
        exposure: Exposure,
        context: Dict[str, Any] = {},
    ) -> astropy.io.fits.Header:
        """Evaluates the header model for an exposure and returns a header.

        Parameters
        ----------
        exposure
            The exposure for which we want to evaluate the model.
        context
            A dictionary of arguments used to evaluate the parameters in
            the model.

        Returns
        -------
        header
            A `~astropy.io.fits.Header`, created by evaluating the model for
            the input exposure.
        """

        header = astropy.io.fits.Header()

        for card in self:

            processed_card = self._process_input(card)
            if processed_card is not None:
                if isinstance(processed_card, Card):
                    header.append(processed_card.evaluate(exposure, context=context))
                elif isinstance(processed_card, (CardGroup, MacroCard)):
                    header += processed_card.to_header(exposure, context=context)

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
                raise CardError(f"Invalid card {card}. This should not have happened.")

        return astropy.table.Table(rows=rows, names=["name", "value", "comment"])
