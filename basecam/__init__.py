# encoding: utf-8
# flake8: noqa

from sdsstools import get_package_version

from .camera import *
from .events import *
from .exceptions import *
from .notifier import EventListener
from .utils import get_config, get_logger


NAME = 'basecam'

__version__ = get_package_version(__file__, 'sdss-basecam') or 'dev'
