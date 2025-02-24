basecam
=======

![Versions](https://img.shields.io/badge/python-3.8-blue)
[![PyPI version](https://badge.fury.io/py/sdss-basecam.svg)](https://badge.fury.io/py/sdss-basecam)
[![Documentation Status](https://readthedocs.org/projects/sdss-basecam/badge/?version=latest)](https://sdss-basecam.readthedocs.io/en/latest/?badge=latest)
[![Test](https://github.com/sdss/basecam/actions/workflows/test.yml/badge.svg)](https://github.com/sdss/basecam/actions/workflows/test.yml)
[![Coverage Status](https://codecov.io/gh/sdss/basecam/branch/master/graph/badge.svg)](https://codecov.io/gh/sdss/basecam)

``basecam`` provides a wrapper around CCD camera APIs with an SDSS-style TCP/IP actor. The main benefits of using `basecam` are:

- Simplifies the creation of production-level camera libraries by providing all the common boilerplate so that you only need to focus on implementing the parts that are specific to your camera API.
- Provides a common API regardless of the underlying camera being handled.
- Powerful event handling and notification.
