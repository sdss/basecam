basecam
=======

![Versions](https://img.shields.io/badge/python-3.7%20|%203.8-blue)
[![Documentation Status](https://readthedocs.org/projects/sdss-basecam/badge/?version=latest)](https://sdss-basecam.readthedocs.io/en/latest/?badge=latest)
[![Travis (.org)](https://img.shields.io/travis/sdss/basecam)](https://travis-ci.org/sdss/basecam)
[![Coverage Status](https://coveralls.io/repos/github/sdss/basecam/badge.svg?branch=master)](https://coveralls.io/github/sdss/basecam?branch=master)

``basecam`` provides a wrapper around CCD camera APIs with an SDSS-style TCP/IP actor. The main benefits of using `basecam` are:

- Simplifies the creation of production-level camera libraries by providing all the common boilerplate so that you only need to focus on implementing the parts that are specific to your camera API.

- Provides a common API regardless of the underlying camera being handled.

- Powerful event handling and notification.
