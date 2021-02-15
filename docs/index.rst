
basecam's documentation
========================

This is the Sphinx documentation for the SDSS Python product `basecam <https://github.com/sdss/basecam>`__. This documentation is for version |basecam_version|.

``basecam`` provides an abstract library for wrapping of astronomical CCD cameras. The goals of this project are:

- To provide a uniform API to control CCD cameras regardless of their specific implementations.
- To reduce code cluttering by abstracting the parts of the implementation that are common to all cameras.
- To provide sever-client access to the camera over TCP-IP or other channels by using `CLU <https://github.com/sdss/clu>`__.
- To reduce the amount of code that needs to be tested to the low-level camera implementation.
- To provide tools to create models for FITS extensions and headers.

``basecam`` is an asynchronous library that uses `asyncio`. ``basecam`` has been developed for use in the `SDSS <https://sdss.org>`__ project but it can be used with any astronomical camera (and, arguably, with any camera).


Contents
--------

.. toctree::
  :maxdepth: 2

  getting-started
  abstract
  exposure
  configuration
  mixins
  actor
  api

  changelog


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
