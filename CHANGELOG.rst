.. basecam-changelog:

=========
Changelog
=========

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
