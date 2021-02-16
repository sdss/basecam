.. basecam-changelog:

=========
Changelog
=========

* :release:`0.4.2 <2021-02-16>`
* :feature:`16` Use JSONSchema validation for actor keyword datamodel. The datamodel of the actor has been updated. The schema should work for all CLU actors, including ``LegacyActor`` although in this case the keywords will be flattened into a list.
* :support:`18` Improve notifications during an exposure.
* :feature:`-` `.CardGroup` now accepts string items that are evaluated to default cards.
* :feature:`-` Complete version of the documentation.

* :release:`0.4.1 <2021-02-13>`
* :feature:`13` Add a `.WCSCards` macro that expands into full WCS header information.
* :feature:`-` Allow `.MacroCard.macro` to return `.Card` or `.CardGroup`.
* :feature:`-` Allow `.HeaderModel` to accept ``None`` as an item. This is useful to programmatically define cards that in some cases may not be added.

* :release:`0.4.0 <2021-02-12>`
* :feature:`-` `.Card` now accepts a ``type`` to which to be cast. By default ``autocast=True`` will try to cast the value to the correct type after evaluating.
* :feature:`-` `.Card` now accepts a default value to which it reverts if the value cannot be evaluated correctly.
* :feature:`-` Allow re-setting the `.ImageNamer` basename dynamically. Call `.ImageNamer` with the camera by default.
* :support:`-` Simplify default cards.
* :support:`-` Format using ``black`` and add type hinting to most of the codebase.

* :release:`0.3.3 <2020-12-07>`
* :support:`-` Retag of 0.3.2 with syntax error fixed.

* :release:`0.3.2 <2020-12-07>`
* :bug:`-` Do not try to set logger format if it failed to create the file logger.

* :release:`0.3.1 <2020-10-31>`
* :support:`-` When ``verbose=False`` set the ``StreamHandler`` level to ``WARNING``.

* :release:`0.3.0 <2020-08-01>`
* :bug:`-` When ``verbose=False`` set the ``StreamHandler`` level to ``ERROR`` to allow tracebacks.
* :feature:`11` *Breaking change.* `.Exposure.write` is now a coroutine and must be awaited if called directly. ``HDUList.writeto()`` is run in an executor.

* :release:`0.2.0 <2020-07-31>`
* :bug:`-` Fix ``CameraWarning`` when used from a ``CameraSystem`` instance.
* :support:`-` Significant refactor. Most functionality is not affected but things are handled a bit differently, with some simplifications.
* :support:`-` Use GitHub Workflows.

* :release:`0.1.1 <2020-01-24>`
* Allow to use ``camera`` substitutions in `.ImageNamer`.
* Use asyncio exception handler in `.Poller`.
* Create intermediate directories when writing file.
* Run ``exposure.write()`` in executor.

* :release:`0.1.0 <2020-01-20>`
* Initial release.
