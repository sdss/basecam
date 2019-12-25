# encoding: utf-8
# flake8: noqa

import pkg_resources

from .camera import *
from .events import *
from .exceptions import *
from .notifier import EventListener
from .utils import get_config, get_logger


try:
    __version__ = pkg_resources.get_distribution('sdss-basecam').version
except pkg_resources.DistributionNotFound:
    __version__ = 'dev'

NAME = 'basecam'
