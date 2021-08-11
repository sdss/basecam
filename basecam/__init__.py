# encoding: utf-8
# flake8: noqa

from sdsstools import get_package_version


NAME = "sdss-basecam"

__version__ = get_package_version(__file__, "sdss-basecam") or "dev"


from .camera import *
from .events import *
from .exceptions import *
from .exposure import *
from .notifier import *
