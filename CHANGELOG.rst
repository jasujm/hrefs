Unreleased
----------

Fixed
 * Fix matching mounted routes in newer versions of Starlette

Version 0.13
------------

Date
  2023-12-05

Changed
 * Refactor ``BaseReferrableModel`` internals. This is mainly for maintainability
   reasons. The API remains the same, but the new implementation removes some
   earlier restrictions, such as forbidding recursive hyperlinks as primary key.

Fixed
 * Support forward references in hyperlinks in ``pydantic`` v2

Version 0.12
------------

Date
  2023-11-18

Added
 * Support Python 3.12
 * Experimental support for ``pydantic`` v2

Changed
 * Failing to parse ``Href`` due to incompatible input type throws
   ``ValueError`` instead of ``TypeError`` to remain compatible with
   ``pydantic`` v2
 * Tests and documentation now refer ``pydantic`` v2 APIs as an alternative,
   whenever the v1 API is deprecated
 * Unparameterized ``Href`` causes error on model definition time, instead of
   model validation time

Deprecated
 * ``Href.__modify_href_schema__()`` and ``Href.validate()`` are only used by
   pydantic v1, and no longer part of the public API

Fixed
 * Unwrapping of path parameters when the model key contains recursive hyperlinks

Version 0.11.1
--------------

Date
  2023-09-01

Changed
 * Specify ``pydantic<2`` in requirements, since the library doesn't yet work
   with ``pydantic>=2``
 * Documentation fixes

Version 0.11
------------

Date
  2023-09-01

Fixed
 * Fixed JSON encoding error with recent FastAPI versions
 * Fixed ``starlette.HrefMiddleware`` not being compatible with lifespans

Deprecated
 * Python 3.7 is EOL. It is still allowed, but no longer tested.

Version 0.10
------------

Date
  2023-03-19

Changed
 * Some configuration errors in the Starlette integration (missing
   ``details_view`` route, model key not compatible with the route parameters
   etc.) now throw a custom ``hrefs.ReferrableModelError`` instead of
   ``pydantic.ValidationError``

Fixed
 * Fixed incorrect documentation
 * Fixed a bug in Starlette integration not correctly finding details view if
   there are mounts
 * Fixed a bug in Starlette integration not correctly handling mounts without
   name

Version 0.9
-----------

Date
  2023-03-17

Changed
 * Clean up and improve unit tests
 * Improve documentation about testing
 * Make ``starlette.HrefMiddleware`` support websocket routes

Fixed
 * Support ``starlette`` version ``0.26.0`` and above

Version 0.8
-----------

Date
  2023-03-05

Added
 * The ``hrefs.model.HrefResolver`` based hyperlink resolution mechanism to
   replace tight coupling between model classes and the web framework
 * Starlette integration now supports routes mounted via sub-application

Fixed
 * Starlette integration silently ignoring some errors when converting URL to
   model key

Deprecated
 * ``hrefs.starlette.ReferrableModel`` since referrable models should now
   inherit ``hrefs.BaseReferrableModel`` directly

Version 0.7
-----------

Date
  2023-02-20

Added
 * Support for query parameters in URLs

Changed
 * Simplified type hints and removed bunch of code requiring suppression of
   ``pylint`` and ``mypy`` warnings

Deprecated
 * ``hrefs.Referrable`` can no longer be used as `PEP 544 protocol
   <https://www.python.org/dev/peps/pep-0544/>`_

Version 0.6.1
-------------

Date
  2023-02-18

Fixed
 * Documentation proofreading

Version 0.6
-----------

Date
  2023-02-18

Added
 * Support Python 3.11

Fixed
 * Proofread documentation
 * Various ``mypy`` and ``pylint`` issues introduced by newer versions of the
   packages

Version 0.5.1
-------------

Date
  2022-03-23

Fixed
  * `.readthedocs.yaml` file syntax

Version 0.5
-----------

Date
  2022-03-22

Added
  * Implement ``Href.__hash__()``
  * ``hypothesis`` build strategy for hyperlinks
  * ``hrefs.starlette.href_context()`` for setting things other than Starlette
    requests as hyperlink context

Version 0.4
-----------

Date
  2022-01-17

Added
  * Support Python 3.10

Changed
  * Use URL type in ``Href`` schema if using ``pydantic`` version 1.9 or later

Fixed
  * Require ``pydantic`` version 1.8 or later, since 1.7 doesn't work with the
    library

Version 0.3.1
-------------

Date
  2021-12-29

Added
  * Updated documentation about inheritance

Fixed
  * Minor documentation fixes
  * Add package metadata back to PKG-INFO

Version 0.3
-----------

Date
  2021-12-27

Added
  * ``tox`` for test automation
  * Support for hyperlinks as model keys

Changed
  * Replace ``get_key_type()`` and ``get_key_url()`` with ``parse_as_key()`` and
    ``parse_as_url()``, respectively

Version 0.2
-----------

Date
  2021-12-17

Added
  * Implement ``Href.__modify_schema__()``
  * Make it possible to configure model key by using ``hrefs.PrimaryKey``
    annotation.

Changed
  * Split ``Referrable.href_types()`` into ``get_key_type()`` and ``get_url_type()``,
    respectively

Version 0.1.2
-------------

Date
  2021-11-20

Added
  * More project metadata

Version 0.1.1
-------------

Date
  2021-11-20

Added
  * ``requirements.txt`` and ``requirements-dev.txt`` to satisfy RTD and give
    dev environment

Version 0.1
-----------

Date
  2021-11-20

Initial version
