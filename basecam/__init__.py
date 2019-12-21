# encoding: utf-8
# flake8: noqa

import pkg_resources

from .camera import *
from .events import *
from .exceptions import *
from .notifier import EventListener


try:
    __version__ = pkg_resources.get_distribution('sdss-basecam').version
except pkg_resources.DistributionNotFound:
    try:
        import toml
        poetry_config = toml.load(open(os.path.join(os.path.dirname(__file__),
                                                    '../pyproject.toml')))
        __version__ = poetry_config['tool']['poetry']['version']
    except Exception:
        warnings.warn('cannot find basecam version. Using 0.0.0.', UserWarning)
        __version__ = '0.0.0'


NAME = 'basecam'
