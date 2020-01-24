#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2020-01-10
# @Filename: base.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

import abc
import functools
import warnings
from contextlib import contextmanager

import astropy.io.fits
import astropy.table
import numpy

from ..exceptions import CardError, CardWarning
from .magic import _MAGIC_CARDS


__all__ = ['FITSModel', 'Extension', 'HeaderModel', 'Card', 'CardGroup', 'MacroCard']


class FITSModel(list):
    """A model representing a FITS image.

    This model defines the data and header for each extension in a FITS
    image. The model can be evaluated for given `.Exposure`, returning a
    fully formed astropy `~astropy.io.fits.HDUList`.

    Parameters
    ----------
    extension : list of `.Extension`
        A list of HDU extensions defined as `.Extension` objects. If none is
        defined, a single, basic extension is added.

    """

    def __init__(self, extensions=None):

        extensions = extensions or []

        list.__init__(self, extensions)

        if len(self) == 0:
            self.append(Extension(data='raw', name='DATA'))

    def to_hdu(self, exposure, context={}):
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

    __VALID_DATA_VALUES = ['raw', 'none']

    def __init__(self, data=None, header_model=None, name=None, compressed=False):

        if isinstance(data, numpy.ndarray):
            self.data = data
        else:
            assert data is None or data in self.__VALID_DATA_VALUES, 'invalid data'
            self.data = data

        self.header_model = header_model

        self.name = name
        self.compressed = compressed

    def __repr__(self):

        return f'<Extension (name={self.name!r}, compressed={self.compressed})>'

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

        if self.data == 'raw':
            data = exposure.data
        elif self.data == 'none':
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

        return f'<HeaderModel {list.__repr__(self)!s}>'

    def _process_input(self, input_card):
        """Processes the input and converts it into a valid card."""

        if isinstance(input_card, (Card, CardGroup, MacroCard)):
            return input_card
        elif isinstance(input_card, (list, tuple)):
            if isinstance(input_card[0], (list, tuple)):
                card = CardGroup(input_card)
            else:
                card = Card(input_card)
            return card
        elif isinstance(input_card, str):
            return Card(input_card)
        else:
            raise CardError(f'invalid input {input_card!r}')

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
                rows.append(('### MACRO', card.__class__.__name__, ''))
            else:
                raise CardError(f'invalid card {card}. '
                                'This should not have happened.')

        return astropy.table.Table(rows=rows, names=['name', 'value', 'comment'])


class Card(object):
    """A card representing a single entry in the header.

    This class is similar to astropy's `~astropy.io.fits.Card` with the
    difference that the value of the card does not need to be a literal and is
    evaluated when `.evaluate` is called.

    The value of the card can be:

    - A Python literal.

    - A callable, with a list of arguments, that is called when the card
      is evaluated.

    - A string using Python's :ref:`python:formatstrings`. As with normal
      strings, the replacement fields are surrounded by ``{`` and ``}`` and
      filled when `.evaluate` is called. The replacement fields can point to an
      attribute, function, method, or property. In addition, it is possible to
      use the string ``__exposure__`` and ``__camera__`` to refer to the
      `.Exposure` instance for which this card will be evaluated, and the
      instance of `.BaseCamera` that took the image, respectively. For example,
      ``value='{__camera__.name}'`` will be replaced with the name of the
      camera, and ``value='{__exposure__.obstime}'`` will retrieve the time of
      the start of the exposure.

    - A string to be evaluated using Python's `eval` function. For example,
      ``value='__camera__.get_temperature()'``.

    If the ``name`` of the card is one of the :ref:`Magic Cards <magic-cards>`,
    the value and comment are automatically defined and do not need to be
    specified.

    Parameters
    ----------
    name : str
        The name of the card. Will be trimmed to 8 characters. Can be one of
        the :ref:`Magic Cards <magic-cards>` names, which defines the value
        and comment.
    value
        A Python literal, callable, or string, as described above.
    comment : str
        A short comment describing the card value.
    fargs : tuple
        If ``value`` is a callable, the arguments to pass to it when it gets
        called. The arguments are evaluated following the same rules as with
        the ``value`` before being passed to the callable.
    evaluate : bool
        If `True`, assumes the value is a string to be evaluated in realtime.
        The context is used as ``locals`` for the evaluation. For security,
        ``globals`` are not available.
    context : dict
        A dictionary of parameters used to fill the value replacement fields.
        Two values, ``__exposure__`` and ``__camera__``, are always defined.
        This context can be updated during the evaluation of the card.

    """

    def __init__(self, name, value=None, comment=None, fargs=None,
                 evaluate=False, context=None):

        if isinstance(name, (list, tuple)):
            try:
                name_ = name[0]
                value = name[1]
                comment = name[2]
                fargs = name[3].get('fargs', None)
                context = name[3].get('context', {})
                evaluate = name[3].get('evaluate', False)
            except IndexError:
                pass
            finally:
                name = name_

        self.name = name

        if len(self.name) > 8:
            warnings.warn(f'trimming {self.name} to 8 characters', CardWarning)
            self.name = self.name[:8]

        if self.is_magic():

            if value:
                raise ValueError(f'cannot override value of magic card {self.name!r}')

            magic_params = _MAGIC_CARDS[self.name.upper()]
            self.value, magic_comment = magic_params[0:2]

            self.comment = comment or magic_comment

            if len(magic_params) == 3:
                fargs = magic_params[2].get('fargs', None)
                context = magic_params[2].get('context', {})
                evaluate = magic_params[2].get('evaluate', False)

        else:

            self.value = value
            self.comment = comment

        self._fargs = fargs
        self._evaluate = evaluate

        self.context = context or {}

    def __repr__(self):

        return f'<Card (name={self.name!r}, value={self.value!r})>'

    def is_magic(self):
        """Returns `True` if the card name matches a magic card."""

        return self.name.upper() in _MAGIC_CARDS

    @contextmanager
    def set_exposure(self, exposure, context={}):
        """Sets the current exposure and context, clearing it on exit."""

        original_context = self.context.copy()

        try:
            self._exposure = exposure
            self.context.update({'__exposure__': self._exposure,
                                 '__camera__': self._exposure.camera})
            self.context.update(context)
            yield
        finally:
            self._exposure = None
            self.context = original_context

    def _render_value(self, value):
        """Returns the value after evaluating the string template."""

        if not isinstance(value, str):
            return value

        if self._evaluate:
            return eval(value, {}, self.context)

        # Expand the placeholders. If there are none, no harm done.
        return value.format(**self.context)

    def _evaluate_callable(self, func, use_fargs=True):
        """Evaluates a value that is a callable function or method."""

        if use_fargs and self._fargs:
            # Evaluate the fargs as values so that we can apply
            # all the magic to them as well.
            fargs = (self._evaluate_value(farg, use_fargs=False)
                     for farg in self._fargs)
            return func(*fargs)

        return func()

    def _evaluate_value(self, value, use_fargs=True):
        """Evaluates a value, expanding its template."""

        if isinstance(value, (list, tuple)):
            return (self._evaluate_value(v) for v in value)

        if callable(value):
            return self._evaluate_callable(value, use_fargs=use_fargs)

        return self._render_value(value)

    def evaluate(self, exposure, context={}):
        """Evaluates the card.

        Evaluates the card value, expanding its template parameters. If the
        value is a callable, calls the function at this time.

        Parameters
        ----------
        exposure : .Exposure
            The exposure for which we want to evaluate the card.
        context : dict
            A dictionary of arguments used to evaluate the parameters in
            the value. These argument update those defined when the `.Card`
            was created.

        Returns
        -------
        tuple
            A tuple with the name, evaluated value, and comment for this card.

        """

        with self.set_exposure(exposure, context):
            rendered_value = self._evaluate_value(self.value)

        return (self.name, rendered_value, self.comment)


class CardGroup(list):
    """A group of `.Card` instances.

    A `.CardGroup` is just a list of `Cards <.Card>` that are grouped for
    convenience and for easy reuse.

    Parameters
    ----------
    cards : list
        A list of `.Card` instances. Elements can also be a tuple of two or
        three elements (for name, value, and optionally a comment).
    name : str
        A name for the card group.
    use_group_title : bool
        Whether to prepend a COMMENT card with the group title when creating
        a header.

    """

    def __init__(self, cards, name=None, use_group_title=True):

        self.name = name
        self.use_group_title = use_group_title

        cards = [self._process_input(card) for card in cards or []]
        list.__init__(self, cards)

    def __repr__(self):

        return f'<CardGroup {list.__repr__(self)!s}>'

    def _process_input(self, card):
        """Processes the input and converts it into a valid card."""

        if isinstance(card, Card):
            return card
        elif isinstance(card, (list, tuple, str)):
            return Card(card)
        else:
            raise CardError(f'invalid card {card}')

    def append(self, card):
        list.append(self, self._process_input(card))

    def insert(self, idx, card):
        list.insert(self, idx, self._process_input(card))

    def evaluate(self, exposure, context={}):
        """Evaluates all the cards.

        Parameters
        ----------
        exposure : .Exposure
            The exposure for which we want to evaluate the cards.
        context : dict
            A dictionary of arguments used to evaluate the cards.

        Returns
        -------
        list
            A list of tuples with the name, evaluated value, and comment
            for each card.

        """

        return [card.evaluate(exposure, context=context) for card in self]

    def to_header(self, exposure, context={}, use_group_title=None):
        """Evaluates all the cards and returns a header.

        Parameters
        ----------
        exposure : .Exposure
            The exposure for which we want to evaluate the cards.
        context : dict
            A dictionary of arguments used to evaluate the cards.
        use_group_title : bool
            Whether to prepend a COMMENT card with the group title when
            creating the header.

        Returns
        -------
        header : `~astropy.io.fits.Header`
            A header composed from the cards in the group.

        """

        header = astropy.io.fits.Header(self.evaluate(exposure, context=context))

        use_group_title = use_group_title or self.use_group_title
        if use_group_title and self.name:
            header.insert(0, ('COMMENT', '{s:#^30}'.format(s=f' {self.name} ')))

        return header


class MacroCard(object, metaclass=abc.ABCMeta):
    """A macro that returns a list of keywords and values.

    This is an abstract class in which the `.macro` method must be overridden
    to return a list of keywords and values that can be used to create a
    header.

    Parameters
    ----------
    name : str
        A name for the macro group.
    use_group_title : bool
        Whether to prepend a COMMENT card with the macro title when creating
        a header.
    kwargs : dict
        Additional arguments for the macro.

    """

    def __init__(self, name=None, use_group_title=True, **kwargs):

        self.name = name
        self.use_group_title = use_group_title
        self.kwargs = kwargs

    def __repr__(self):

        return f'<{self.__class__.__name__ (name=self.name)}>'

    @abc.abstractmethod
    def macro(self, exposure, context={}):
        """The macro.

        Must return a list of tuples with the format
        ``(keyword, value, comment)`` or ``(keyword, value)``.

        Parameters
        ----------
        exposure : .Exposure
            The exposure for which we want to evaluate the macro.
        context : dict
            A dictionary of parameters that can be used by the macro.

        """

        raise NotImplementedError

    def evaluate(self, exposure, context={}):
        """Evaluates the macro. Equivalent to calling `.macro` directly.

        Parameters
        ----------
        exposure : .Exposure
            The exposure for which we want to evaluate the macro.
        context : dict
            A dictionary of parameters that can be used by the macro.

        Returns
        -------
        cards : `list`
            A list of tuples with the format ``(keyword, value, comment)``
            or ``(keyword, value)``.

        """

        return self.macro(exposure, context=context)

    def to_header(self, exposure, context={}, use_group_title=None):
        """Evaluates the macro and returns a header.

        Parameters
        ----------
        exposure : .Exposure
            The exposure for which we want to evaluate the macro.
        context : dict
            A dictionary of arguments used to evaluate the macro.
        use_group_title : bool
            Whether to prepend a COMMENT card with the macro title when
            creating the header.

        Returns
        -------
        header : `~astropy.io.fits.Header`
            A header composed from the cards in the macro.

        """

        header = astropy.io.fits.Header(self.evaluate(exposure, context=context))

        use_group_title = use_group_title or self.use_group_title
        if use_group_title and self.name:
            header.insert(0, ('COMMENT', '{s:#^30}'.format(s=f' {self.name} ')))

        return header
