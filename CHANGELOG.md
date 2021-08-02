# Changelog

## 0.5.1 - Aug 2, 2021

### ✨ Improved

* Use `furo` and `myst-parser` for the documentation.
* `ImageNamer`: allow to reset the sequence number when the directory changes.


## 0.5.0 - May 16, 2021

### 🚀 New

* [#19](https://github.com/sdss/basecam/issues/19) `Extension` now accepts `compression_params` that are passed to `CompImageHDU`.
* [#20](https://github.com/sdss/basecam/issues/20) Allow to dynamically add extra HDUs to `Exposure`.
* [#21](https://github.com/sdss/basecam/issues/21) Allow to pass extra arguments to `_expose_internal` from the actor command.
* Make `BaseCamera.notify` a public method.
* [#22](https://github.com/sdss/basecam/issues/22) Add optional post-process step during exposure.
* Add hook to invoke a post-process callback coroutine in the `expose` actor command.
* Add `get_schema` to retrieve the actor schema as a dictionary.

### ✨ Improved

* Update CLU to `^1.0.0`.


## 0.4.2 - February 16, 2021

### 🚀 New

* [#16](https://github.com/sdss/basecam/issues/16) Use JSONSchema validation for actor keyword datamodel. The datamodel of the actor has been updated. The schema should work for all CLU actors, including `LegacyActor` although in this case the keywords will be flattened into a list.
* `CardGroup` now accepts string items that are evaluated to default cards.
* Complete version of the documentation.

### ✨ Improved

* [#18](https://github.com/sdss/basecam/issues/18) Improve notifications during an exposure.


## 0.4.1 - February 13, 2021

### 🚀 New

* [#13](https://github.com/sdss/basecam/issues/13) Add a `WCSCards` macro that expands into full WCS header information.
* Allow `MacroCard.macro` to return `Card` or `CardGroup`.
* Allow `HeaderModel` to accept `None` as an item. This is useful to programmatically define cards that in some cases may not be added.


## 0.4.0 - February 12, 2021

### 🚀 New

* `Card` now accepts a `type` to which to be cast. By default `autocast=True` will try to cast the value to the correct type after evaluating.
* `Card` now accepts a default value to which it reverts if the value cannot be evaluated correctly.
* Allow re-setting the `ImageNamer` basename dynamically. Call `ImageNamer` with the camera by default.

### ✨ Improved

* Simplify default cards.
* Format using `black` and add type hinting to most of the codebase.


## 0.3.3 - December 7, 2020

### 🔧 Fixed

* Retag of 0.3.2 with syntax error fixed.


## 0.3.2 - December 7, 2020

### 🔧 Fixed

* Do not try to set logger format if it failed to create the file logger.


## 0.3.1 - October 31, 2020

### ✨ Improved

* When `verbose=False` set the `StreamHandler` level to `WARNING`.


## 0.3.0 - August 1, 2020

### 🚀 New

* [#11](https://github.com/sdss/basecam/issues/11) **Breaking change.** `Exposure.write` is now a coroutine and must be awaited if called directly. `HDUList.writeto()` is run in an executor.

### 🔧 Fixed

* When `verbose=False` set the `StreamHandler` level to `ERROR` to allow tracebacks.


## 0.2.0 - July 31, 2020

### ✨ Improved

* Significant refactor. Most functionality is not affected but things are handled a bit differently, with some simplifications.
* Use GitHub Workflows.

### 🔧 Fixed

* Fix `CameraWarning` when used from a `CameraSystem` instance.


## 0.1.1 - January 24, 2020

### ✨ Improved

* Allow to use `camera` substitutions in `ImageNamer`.
* Use asyncio exception handler in `Poller`.
* Create intermediate directories when writing file.
* Run `exposure.write()` in executor.


## 0.1.0 - January 20, 2020

### 🚀 New

* Initial release.
