.. basecam-changelog:

=========
Changelog
=========

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
