.. _exposure:

Exposures
=========

One of the strengths of ``basecam`` is that it allows to define a datamodel for the camera exposures, which is evaluated when the exposure is written. The datamodel is built upon three basic concepts: `Cards <.Card>` which represent a header keyword-value pair; `Extensions <.Extension>` which represent a FITS extension with a `header <.HeaderModel>` defined by cards, and specify how the data will be stored; and a `FITS model <.FITSModel>` which bundles up several extensions.

Each camera class and instance has an associated FITS model. When the camera `~.BaseCamera.expose` method in a camera is called, it returns an `.Exposure` object that includes the image data and additional metadata (exposure time, date of observation, stacking). When the exposure is written, the model is evaluated for that specific exposure and camera.

.. code-block::

    >>> exposure = await camera.expose(1.0)
    >>> type(exposure.fits_model)
    basecam.models.fits.FITSModel
    >>> exposure.fits_model
    [<Extension (name='raw', compressed=GZIP_2)>]
    >>> list(exposure.fits_model[0].header_model)
    [<DefaultCard (name='CAMNAME', value='{__camera__.name}')>,
     <DefaultCard (name='VCAM', value='{__camera__.__version__}')>,
     <DefaultCard (name='IMAGETYP', value='{__exposure__.image_type}')>,
     <DefaultCard (name='EXPTIME', value='{__exposure__.exptime}')>,
     <DefaultCard (name='EXPTIMEN', value='{__exposure__.exptime_n}')>,
     <DefaultCard (name='STACK', value='{__exposure__.stack}')>,
     <DefaultCard (name='STACKFUN', value='{__exposure__.stack_function.__name__}')>,
     <Card (name='TIMESYS', value='TAI')>,
     <Card (name='DATE-OBS', value='{__exposure__.obstime.tai}')>,
     <Card (name='CCDTEMP', value='{__camera__.status[temperature_ccd]}')>,
     <WCSCards (name=WCS information)>]

If we convert the exposure to an `~astropy.io.fits.HDUList` ::

    >>> hdulist = exposure.to_hdu()
    >>> hdulist[1].header
    XTENSION= 'IMAGE   '           / Image extension
    BITPIX  =                   16 / data type of original image
    NAXIS   =                    2 / dimension of original image
    NAXIS1  =                 2048 / length of original image axis
    NAXIS2  =                 2048 / length of original image axis
    PCOUNT  =                    0 / number of parameters
    GCOUNT  =                    1 / number of groups
    BSCALE  =                    1
    BZERO   =                32768
    CAMNAME = 'gfa0    '           / Camera name
    VCAM    = '0.2.0-alpha.0'      / Version of the camera library
    IMAGETYP= 'object  '           / The image type of the file
    EXPTIME =                  1.0 / Exposure time of single integration [s]
    EXPTIMEN=                  1.0 / Total exposure time [s]
    STACK   =                    1 / Number of stacked frames
    STACKFUN= 'median  '           / Function used for stacking
    TIMESYS = 'TAI     '           / Time reference system
    DATE-OBS= '2021-02-15 06:42:59.592779' / Time of the start of the exposure [TAI]
    CCDTEMP =                -25.0 / Degrees C
    WCSAXES =                    2 / Number of coordinate axes
    CRPIX1  =                  0.0 / Pixel coordinate of reference point
    CRPIX2  =                  0.0 / Pixel coordinate of reference point
    CDELT1  =                  1.0 / Coordinate increment at reference point
    CDELT2  =                  1.0 / Coordinate increment at reference point
    CRVAL1  =                  0.0 / Coordinate value at reference point
    CRVAL2  =                  0.0 / Coordinate value at reference point
    LATPOLE =                 90.0 / [deg] Native latitude of celestial pole
    MJDREF  =                  0.0 / [d] MJD of fiducial time
    CHECKSUM= '7aV5AXS37aS3AUS3'   / HDU checksum updated 2021-02-14T22:42:23
    DATASUM = '3919376360'         / data unit checksum updated 2021-02-14T22:42:23

Cards
-----

A card is simply a tuple of ``(name, value)`` or ``(name, value, comment)`` that defines a header keyword-value pair. In that sense they are similar to astropy's `~astropy.io.fits.Card` objects. The main difference is that in ``basecam`` cards, the value can be defined as a placeholder that is evaluated in runtime. For example ::

    >>> import datetime
    >>> card = Card('DATE', '{date}', 'Some date')
    >>> now = datetime.datetime.utcnow()
    >>> card.evaluate(None, context={'date': now})
    EvaluatedCard(name='date', value='2021-02-15 07:03:24.024889', comment='Some date')

Values can be defined following the same syntax as `Python's string templates <https://docs.python.org/3/reference/lexical_analysis.html#f-strings>`__. The values of the placeholders are specified via the ``context``. The context can be specified at the moment of evaluating the card, but normally it's defined at the FITS model level and passed down when evaluating the model for a given exposure. Note that we called `~.Card.evaluate` with ``None`` as the first argument; normally `~.Card.evaluate` is called with an `.Exposure` instance. In this case two context parameters are automatically defined: ``__exposure__``, which is replaced with the `.Exposure` object, and ``__camera__`` which is replaced with the camera that took the exposure. This allows us to define more useful cards ::

    >>> exptime = Card('EXPTIME', '{__exposure__.exptime}', 'Exposure time')
    >>> exptime.evaluate(exposure)
    EvaluatedCard(name='EXPTIME', value=900., comment='Exposure time')
    >>> camname = Card('CAMNAME', '{__camera__.name}', 'Camera name')
    >>> camname.evaluate(exposure)
    EvaluatedCard(name='CAMNAME', value='gfa1', comment='Camera name')

We can access any attribute or property of the context placeholders ::

    >>> Card('CCDTEMP', '{__camera__.status[ccdtemp]}').evaluate(exposure)
    EvaluatedCard(name='CCDTEMP', value=-30.1, comment='')

Note that in this case we don't need to use quotes around ``status[ccdtemp]``. Again, this is in line with Python's string formatting.

By default, when the card is evaluated ``basecam`` will try to cast the value to a valid FITS type, or fall back to a string if that's not possible. This can be disabled by passing ``autocast=False`` ::

    >>> Card('CCDTEMP', '5.0').evaluate(exposure)
    EvaluatedCard(name='CCDTEMP', value=5, comment='')
    >>> Card('CCDTEMP', '5.0', autocast=False).evaluate(exposure)
    EvaluatedCard(name='CCDTEMP', value='5.0', comment='')

It's also possible to specify the casting type (this implies ``autocast=False``) ::

    >>> Card('CCDTEMP', '{__camera__.status[ccdtemp]}', type=int).evaluate(exposure)
    EvaluatedCard(name='CCDTEMP', value=-30, comment='')

The value can be a function that is called at the time of evaluation ::

    def f():
        return 10

    >>> Card('FUNC', f).evaluate(exposure)
    EvaluatedCard(name='FUNC', value=10, comment='')

In this case we can define arguments to be passed to the function, and those arguments can also be evaluated in runtime (note that in this case the arguments will be strings so the function needs to do the casting if necessary) ::

    def square(value):
        return float(value)**2

    >>> Card('SQEXPTIM', square, fargs=['{__exposure__.exptime}']).evaluate(exposure)
    EvaluatedCard(name='SQEXPTIM', value=25.0, comment='')

Value expressions can be evaluated ::

    >>> Card('SUM', "2+2", evaluate=True).evaluate(None)
    EvaluatedCard(name='SUM', value=4, comment='')

In this case the variables in the context are accessible as local variables ::

    >>> Card('CCDF', "__camera__.status[ccdtemp]*9/5+32", comment='CCD temperature in Fahrenheit').evaluate(exposure)
    EvaluatedCard(name='CCDF', value=-25.6, comment='CCD temperature in Fahrenheit')

Note that in this case we don't use curly brackets around the variables.

.. _default-cards:

Default cards
^^^^^^^^^^^^^

``basecam`` defines a number of cards that are of general use. They are available at `.DEFAULT_CARDS` and can be retrieved by creating a `.Card` with the name of the default card and without a value. For example ::

    >>> obstime = Card('obstime')
    >>> obstime
    DefaultCard("OBSTIME", value="{__exposure__.obstime.tai}", comment="Time of the start of the exposure [TAI]")

Advanced cards
^^^^^^^^^^^^^^

`.Card` is very versatile but there are a couple other types of card classes that are also useful.

`.CardGroup` allows to define a list of `.Card` or default cards that is expanded when evaluated. This is useful to define cards that share a topic and allows reusability ::

    >>> camcards = CardGroup(
        [
            "CAMNAME",
            Card("MODEL", "{__camera__.model}", "Camera model")]),
            ("VENDOR", "{__camera__.vendor}", "Camera manufacturer")
        ]
    )

This assumes that the camera class has attributes ``model`` and ``vendor`` that have been set when the camera connects. Cards in the group can be defined as a single string which must be the name of a default card, or as a two- or three-item tuple that is evaluated to ``(key, value, [comment])``.

`.MacroCard` classes provide more flexibility to create cards or groups of cards. Let's assume the code has access to some weather service ``weather``. We can create a macro that returns a list of cards with weather information ::

    class WeatherCards(MacroCard):
        def macro(self, exposure, context={}):
            truss_temp = weather.get_truss_temp()
            rh = weather.get_humid()
            dew_point = truss_temp - ((100 - rh) / 5.)
            return [('TEMP', truss_temp, 'Truss temperature (C)'),
                    ('RELHUM', rh, 'Relative humidity (%)'),
                    ('DEWPOINT', dew_point, 'Dew point temperature (C)')]

`.MacroCard` needs to be subclassed and ``macro`` must be overridden with a method that returns a list of tuples. Macros are specially useful when combined with :ref:`actors <Actor>` that have access to the state of the system. They can be used to, for example, add information about the telescope position and status.

WCS macro
^^^^^^^^^

``basecam`` includes a predefined `.WCSCards` macro that returns a complete set of WCS astrometric cards. When used, the ``wcs`` attribute in the exposure must be set to a valid `~astropy.wcs.WCS` object. This is usually done in ``_exposure_internal`` or before calling `.Exposure.to_hdu` or `.Exposure.write`. If ``Exposure.wcs=None`` a default WCS header is added.

FITS models
-----------

A `FITS model <.FITSModel>` is equivalent to an `~astropy.io.fits.HDUList`, consisting of a list of `.Exposure`, each one defining its own `header model <.HeaderModel>`. Let's start with a simple example ::

    >>> header = HeaderModel(
        [
            "CAMNAME",
            "CAMUID",
            "IMAGETYP",
            "EXPTIME",
            Card("DATE-OBS", value="{__exposure__.obstime.tai.isot}", comment="Date (in TIMESYS) the exposure started")
            WeatherCards()
        ]
    )
    >>> model = FITSModel([Extension(header_model=header, name="PRIMARY")])

We've defined a header model with several default cards (``CAMNAME``, ``CAMUID``, etc.), one card to record the time of the observation in ISOT format, and the ``WeatherCards`` macro that we defined above. Next, we created a FITS model with a single extension which we called ``"PRIMARY"``. To use this model when exposing, we can ::

    >>> exposure = await camera.expose(15.0, fits_model=model)

or we can set it in the `.Exposure` instance as ``exposure.fits_model=model``. The model will then be used when `.Exposure.to_hdu` or `.Exposure.write` are called.

In `.Extension` we can define the format of the data. To create an empty extension with a header ::

    >>> empty_ext = Extension(data='none', header_model=header, name="EMPTY")

If ``data=None`` (the default), ``Exposure.data`` will be used to create the image HDU. We can define a compressed HDU ::

    >>> compressed = Extension(header_model=header, compressed="RICE_1")

The available compression algorithms are the same as astropy's `~astropy.io.fits.CompImageHDU`. Compressed HDUs cannot be the primary header of a FITS file, so in this case an empty HDU will be prepended as the primary extension.

Naming images
-------------

`.Exposure` filenames can be defined manually or using an `.ImageNamer` instance. The image namer allows to define a file path that is evaluated at the time at which the image is written ::

    >>> image_namer = ImageNamer('{camera.name}-{num:04d}.fits', dirname='/data/images/{date.mjd}')
    >>> img_path = image_namer(camera)
    >>> print(img_path)
    '/data/images/59260/gfa1-0012.fits'
    >>> exposure.write(img_path)
    >>> image_namer(camera)
    '/data/images/59260/gfa1-0013.fits'

As with the cards, two values can be used in the templates: the ``camera`` instance, and the ``date`` (an astropy `~astropy.time.Time` object) when the image namer is called. The ``num`` placeholder can be used to get the first available number in a sequence of images, ensuring that the new path doesn't collide with any previous image.

Modifying the default model and image namer
-------------------------------------------

`.BaseCamera` includes a default FITS model and image namer which are mean to provide general but basic functionality. The `default model <.basic_fits_model>` defines a single, uncompressed extension with the raw data and a `basic header model <.basic_header_model>`. The default image namer writes returns new image paths in the current directory with format ``'{camera.name}-{num:04d}.fits'``.

While these are reasonable defaults, normally one wants to customise the model and namer for a given camera class. This can be achieved when subclassing from `.BaseCamera` ::

    class MyCamera(BaseCamera):
        fits_model = my_fits_model
        image_namer = my_image_namer

        def __init__(self, *args, **kwargs):
            ...

The image namer can also be defined when instantiating a new camera: ``my_camera=MyCamera(..., image_namer=another_image_namer, ...)``.
