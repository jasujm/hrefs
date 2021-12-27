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
