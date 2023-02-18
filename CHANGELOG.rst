Version 0.6
-----------

Date
  2023-02-18

Added
 * Support Python 3.10

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
