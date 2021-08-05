#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# @Author: José Sánchez-Gallego (gallegoj@uw.edu)
# @Date: 2021-02-10
# @Filename: card.py
# @License: BSD 3-clause (http://www.opensource.org/licenses/BSD-3-Clause)

from __future__ import annotations

import abc
import re
import warnings
from collections.abc import Iterable
from contextlib import contextmanager

from typing import Any, Dict, List, NamedTuple, Optional, Union, cast

import astropy.io.fits
import astropy.wcs

from basecam import __version__

from ..exceptions import CardError, CardWarning
from ..exposure import Exposure


__all__ = [
    "Card",
    "DefaultCard",
    "CardGroup",
    "MacroCard",
    "WCSCards",
    "DEFAULT_CARDS",
]


class EvaluatedCard(NamedTuple):
    """A tuple describing the result of evaluating a `.Card`."""

    name: str
    value: Any
    comment: str


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

    If the ``name`` of the card is one of the :ref:`Default Cards <default-cards>`,
    the value and comment are automatically defined and do not need to be
    specified.

    Parameters
    ----------
    name
        The name of the card. Will be trimmed to 8 characters. Can be one of
        the :ref:`Default Cards <default-cards>` names, which defines the value
        and comment.
    value
        A Python literal, callable, or string, as described above.
    comment
        A short comment describing the card value.
    default
        Default value to use if the card value contains placeholders that are not
        provided while the card is evaluated.
    type
        The type of the card value. The value will be casted after processing.
    autocast
        If `True` and ``type`` is not defined, tries to cast the value.
    fargs
        If ``value`` is a callable, the arguments to pass to it when it gets
        called. The arguments are evaluated following the same rules as with
        the ``value`` before being passed to the callable.
    evaluate
        If `True`, assumes the value is a string to be evaluated in realtime.
        The context is used as ``locals`` for the evaluation. For security,
        ``globals`` are not available.
    context
        A dictionary of parameters used to fill the value replacement fields.
        Two values, ``__exposure__`` and ``__camera__``, are always defined.
        This context can be updated during the evaluation of the card.
    """

    def __new__(cls, name: Union[str, Iterable[Any]], *args, **kwargs):

        if isinstance(name, str):
            if cls == Card and name.upper() in DEFAULT_CARDS:
                if len(args) == 0 and len(kwargs) == 0:
                    return DEFAULT_CARDS[name.upper()]
            return super().__new__(cls)

        return cls(*name)

    def __init__(
        self,
        name: Union[str, Iterable[Any]],
        value: Any = "",
        comment: str = "",
        type: Optional[type] = None,
        autocast: bool = True,
        default: Any = None,
        fargs: Optional[tuple] = None,
        evaluate: bool = False,
        context: Dict[str, Any] = {},
    ):

        if hasattr(self, "name"):
            return

        assert isinstance(name, str)

        self.name = name
        if len(self.name) > 8:
            warnings.warn(f"trimming {self.name} to 8 characters", CardWarning)
            self.name = self.name[:8]

        self.value = value
        self.comment = comment

        self._default = default
        self._type = type
        self._autocast = autocast
        self._fargs = fargs
        self._evaluate = evaluate

        self.context = context or {}

    def __repr__(self):
        return f"<{self.__class__.__name__} (name={self.name!r}, value={self.value!r})>"

    @contextmanager
    def set_exposure(self, exposure, context={}):
        """Sets the current exposure and context, clearing it on exit."""

        original_context = self.context.copy()

        try:
            self._exposure = exposure
            self.context.update({"__exposure__": self._exposure})
            if hasattr(self._exposure, "camera") and self._exposure.camera:
                self.context.update({"__camera__": self._exposure.camera})
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

        # Get a list of the placeholders, if any.
        placeholders = re.findall(r"{([0-9a-zA-Z_]+)\.?.*?}", value)

        if not all([p in self.context for p in placeholders]):
            if self._default:
                return self._default
            else:
                raise ValueError(
                    "The context does not include all the Card value placeholders."
                )

        # Expand the placeholders. If there are none, no harm done.
        return value.format(**self.context)

    def _evaluate_callable(self, func, use_fargs=True):
        """Evaluates a value that is a callable function or method."""

        if use_fargs and self._fargs:
            # Evaluate the fargs as values so that we can apply
            # all the magic to them as well.
            fargs = (
                self._evaluate_value(farg, use_fargs=False) for farg in self._fargs
            )
            return func(*fargs)

        return func()

    def _evaluate_value(self, value, use_fargs=True):
        """Evaluates a value, expanding its template."""

        if callable(value):
            return self._evaluate_callable(value, use_fargs=use_fargs)

        return self._render_value(value)

    def evaluate(
        self,
        exposure: Exposure,
        context: Dict[str, Any] = {},
    ) -> EvaluatedCard:
        """Evaluates the card.

        Evaluates the card value, expanding its template parameters. If the
        value is a callable, calls the function at this time.

        Parameters
        ----------
        exposure
            The exposure for which we want to evaluate the card.
        context
            A dictionary of arguments used to evaluate the parameters in
            the value. These argument update those defined when the `.Card`
            was created.

        Returns
        -------
        EvaluatedCard
            A tuple with the name, evaluated value, and comment for this card.
        """

        with self.set_exposure(exposure, context):
            try:
                rendered_value = self._evaluate_value(self.value)
            except BaseException:
                if self._default:
                    rendered_value = self._default
                else:
                    raise

        if self._type:
            rendered_value = self._type(rendered_value)
        elif self._autocast and isinstance(rendered_value, str):
            rendered_value = cast(str, rendered_value)
            if re.match("^true$", rendered_value, re.IGNORECASE):
                rendered_value = True
            elif re.match("^false$", rendered_value, re.IGNORECASE):
                rendered_value = False
            elif re.match("^none$", rendered_value, re.IGNORECASE):
                rendered_value = self._default if self._default else "None"
            else:
                try:
                    rendered_value = int(rendered_value)
                except ValueError:
                    try:
                        rendered_value = float(rendered_value)
                    except ValueError:
                        pass

        return EvaluatedCard(self.name, rendered_value, self.comment)


class CardGroup(list):
    """A group of `.Card` instances.

    A `.CardGroup` is just a list of `Cards <.Card>` that are grouped for
    convenience and for easy reuse.

    Parameters
    ----------
    cards
        A list of `.Card` instances. Elements can also be a tuple of two or
        three elements (for name, value, and optionally a comment) or a string with
        a default card.
    name
        A name for the card group.
    use_group_title
        Whether to prepend a COMMENT card with the group title when creating
        a header.
    """

    name: Optional[str] = None

    def __init__(
        self,
        cards: Iterable[Union[Card, Iterable, str]],
        name: Optional[str] = None,
        use_group_title: bool = True,
    ):

        self.name = name or self.name
        self.use_group_title: bool = use_group_title

        cards = [self._process_input(card) for card in cards or []]
        list.__init__(self, cards)

    def __repr__(self):

        return f"<CardGroup {list.__repr__(self)!s}>"

    def _process_input(self, card: Union[Card, Iterable]):
        """Processes the input and converts it into a valid card."""

        if isinstance(card, Card):
            return card
        elif isinstance(card, (Iterable, str)):
            return Card(card)
        else:
            raise CardError(f"invalid card {card}")

    def append(self, card: Card):
        list.append(self, self._process_input(card))

    def insert(self, idx, card: Card):
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

    def to_header(
        self,
        exposure: Exposure,
        context: Dict[str, Any] = {},
        use_group_title: bool = False,
    ) -> astropy.io.fits.Header:
        """Evaluates all the cards and returns a header.

        Parameters
        ----------
        exposure
            The exposure for which we want to evaluate the cards.
        context
            A dictionary of arguments used to evaluate the cards.
        use_group_title
            Whether to prepend a COMMENT card with the group title when
            creating the header.

        Returns
        -------
        header
            A header composed from the cards in the group.
        """

        header = astropy.io.fits.Header(self.evaluate(exposure, context=context))

        use_group_title = use_group_title or self.use_group_title
        if use_group_title and self.name:
            header.insert(0, ("COMMENT", "{s:#^30}".format(s=f" {self.name} ")))

        return header


class MacroCard(object, metaclass=abc.ABCMeta):
    """A macro that returns a list of keywords and values.

    This is an abstract class in which the `.macro` method must be overridden
    to return a list of keywords and values that can be used to create a
    header.

    Parameters
    ----------
    name
        A name for the macro group.
    use_group_title
        Whether to prepend a COMMENT card with the macro title when creating
        a header.
    kwargs
        Additional arguments for the macro.
    """

    name = None

    def __init__(
        self,
        name: Optional[str] = None,
        use_group_title: bool = False,
        **kwargs,
    ):

        self.name = name or self.name
        self.use_group_title = use_group_title
        self.kwargs = kwargs

    def __repr__(self):

        return f"<{self.__class__.__name__} (name={self.name})>"

    @abc.abstractmethod
    def macro(self, exposure: Exposure, context: Dict[str, Any] = {}):
        """The macro.

        Must return a list of item which can be tuples with the format
        ``(keyword, value, comment)`` or ``(keyword, value)``, `.Card` instances,
        or `.CardGroup` instances. Cards and card groups will be evaluated.

        Parameters
        ----------
        exposure
            The exposure for which we want to evaluate the macro.
        context
            A dictionary of parameters that can be used by the macro.
        """

        raise NotImplementedError

    def evaluate(self, exposure: Exposure, context: Dict[str, Any] = {}) -> List[tuple]:
        """Evaluates the macro. Equivalent to calling `.macro` directly.

        Parameters
        ----------
        exposure
            The exposure for which we want to evaluate the macro.
        context
            A dictionary of parameters that can be used by the macro.

        Returns
        -------
        tuples
            A list of tuples with the format ``(keyword, value, comment)``
            or ``(keyword, value)``.
        """

        cards = self.macro(exposure, context=context)
        new_cards = []
        for card in cards:
            if isinstance(card, Card):
                new_cards.append(card.evaluate(exposure, context=context))
            elif isinstance(card, CardGroup):
                new_cards += card.evaluate(exposure, context=context)
            else:
                new_cards.append(card)
        return new_cards

    def to_header(
        self,
        exposure: Exposure,
        context: Dict[str, Any] = {},
        use_group_title=False,
    ) -> astropy.io.fits.Header:
        """Evaluates the macro and returns a header.

        Parameters
        ----------
        exposure
            The exposure for which we want to evaluate the macro.
        context
            A dictionary of arguments used to evaluate the macro.
        use_group_title
            Whether to prepend a COMMENT card with the macro title when
            creating the header.

        Returns
        -------
        header
            A header composed from the cards in the macro.
        """

        header = astropy.io.fits.Header(self.evaluate(exposure, context=context))

        use_group_title = use_group_title or self.use_group_title
        if use_group_title and self.name:
            header.insert(0, ("COMMENT", "{s:#^30}".format(s=f" {self.name} ")))

        return header


class WCSCards(MacroCard):
    """A macro that adds WCS header information.

    To use, just add ``WCSCards()`` to the header model and make sure the
    ``Exposure.wcs`` is set. If ``Exposure.wcs=None``, a default WCS header will
    be added.
    """

    name = "WCS information"

    def macro(self, exposure: Exposure, context: Dict[str, Any] = {}):
        if exposure.wcs is None:
            wcs = astropy.wcs.WCS()
        else:
            wcs = exposure.wcs
        return list(wcs.to_header().cards)


class DefaultCard(Card):
    pass


#: Default cards
DEFAULT_CARDS: Dict[str, DefaultCard] = {
    "EXPTIME": DefaultCard(
        "EXPTIME",
        value="{__exposure__.exptime}",
        comment="Exposure time of single integration [s]",
        type=float,
    ),
    "EXPTIMEN": DefaultCard(
        "EXPTIMEN",
        value="{__exposure__.exptime_n}",
        comment="Total exposure time [s]",
        default=-999,
    ),
    "STACK": DefaultCard(
        "STACK",
        value="{__exposure__.stack}",
        comment="Number of stacked frames",
        default=1,
        type=int,
    ),
    "STACKFUN": DefaultCard(
        "STACKFUN",
        value="{__exposure__.stack_function.__name__}",
        comment="Function used for stacking",
        default="NA",
    ),
    "OBSTIME": DefaultCard(
        "OBSTIME",
        value="{__exposure__.obstime.tai}",
        comment="Time of the start of the exposure [TAI]",
    ),
    "IMAGETYP": DefaultCard(
        "IMAGETYP",
        value="{__exposure__.image_type}",
        comment="The image type of the file",
    ),
    "CAMNAME": DefaultCard(
        "CAMNAME",
        value="{__camera__.name}",
        comment="Camera name",
        default="NA",
    ),
    "CAMUID": DefaultCard(
        "CAMUID",
        value="{__camera__.uid}",
        comment="Camera UID",
        default="NA",
    ),
    "VCAM": DefaultCard(
        "VCAM",
        value="{__camera__.__version__}",
        comment="Version of the camera library",
        default="NA",
    ),
    "BASECAMV": DefaultCard(
        "BASECAMV",
        value=__version__,
        comment="Basecam version",
        default="NA",
    ),
}
