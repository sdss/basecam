# Changelog

## Next version

### ⚙️ Engineering

* Use `uv` for dependency management.
* Update workflows and RTDs.


## 0.8.0 - January 16, 2024

### ✨ Improved

* Cast output ``exposure_time`` to float.

### ⚙️ Engineering

* Lint using `ruff`.
* Update workflows.
* Update RTD config and docs building.


## 0.7.2 - April 27, 2023

### ✨ Improved

* Improved overwritting of `BSCALE` and `BZERO` for compressed headers.
* Cast data to `float32` before stacking multiple exposures.


## 0.7.1 - March 10, 2023

### ✨ Improved

* Updated to using `sdss-clu 2.0.0`.


## 0.7.1b1 - March 10, 2023

### ✨ Improved

* Updated to using `sdss-clu 2.0.0b2`.


## 0.7.0 - December 22, 2022

### 💥 Breaking changes

* Dropped Python 3.7 to allow newer versions of `numpy` and `scipy`. `numpy` is not explicitely in the requirements and is installed by `astropy` (see [#31](https://github.com/sdss/basecam/issues/31)).

### ✨ Improved

* Compress gzipped FITS file in temporary directory before moving it to the final location.


## 0.6.3 - June 29, 2022

### 🔧 Fixed

* Fix the use of `--count` with the `expose` command.
* [#28](https://github.com/sdss/basecam/issues/28) Deal with `numpy.asscalar` being deprecated in `numpy` 1.23. Restricted `numpy<1.22.0` to prevent `astropy` 4 running along with `numpy` 1.23.


## 0.6.2 - June 4, 2022

### ✨ New

* Adjust dependencies to support Python 3.10

### 🔧 Fixed

* Force `sdsstools>=0.5.2` to fix the calculation of SJD.


## 0.6.1 - June 4, 2022

### ✨ Improved

* Support defining a card in `HeaderModel` with a list `(name, value, [comment])`, e.g., `header_model.append(("BIASFILE", "/data/bias.fits"))`.


## 0.6.0 - June 4, 2022

### 🚀 New

* [#26](https://github.com/sdss/basecam/issues/26) The `dirname` in an `ImageNamer` now accepts the `{sjd}` placeholder which will be filled out with the SDSS-style MJD (as returned by sdsstools `get_sjd()`).

### 🔧 Fixed

* Prevent a problem in which if an exposure fails with an uncaught error the listener callback was not removed, which would cause duplicate messages being output in successive exposures.
* Try and except when saving exposures to disk.
* Fix case in actor when camera fails to return status.
* Issues with zero seconds exposure time.


## 0.5.4 - January 7, 2022

### 🚀 New

* Allow to list available cameras.
* Make expose command unique.

### 🔧 Fixed

* Really (I hope) fixed the issue with compressed headers.


## 0.5.3 - December 14, 2021

### 🚀 New

* Added a `--count` flag to the `expose` command to issue a number of continous exposures.
* It's now possible to pass a `-n` flag to `expose` to se the sequence number of the exposure. Useful when commanding multiple cameras that one wants to keep in sync.

### 🔧 Fixed

* Finally (?) fixed the problem of compressed headers not being read by some software like JS9. The solution is a bit of a hack that requires updating the file headers after writing them, but seems to work fine.


## 0.5.2 - November 24, 2021

### ✨ Improved

* Add `basecam` version to default header.
* Prevent isse when multiple cameras try to create the same directory at once.


## 0.5.1 - August 2, 2021

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
