.. _api:

API reference
=============

This API reference is intended mainly for developers and people looking for
in-depth description of the different classes and functions. If you simply want
to configure models and parse values into hyperlinks, :ref:`quickstart` gives a
better introduction to using the library.

.. module:: hrefs

Fundamentals
------------

The two main building blocks of the :mod:`hrefs` library are

* :class:`Href`, the class representing hyperlinks

* :class:`Referrable`, the abstract base class of types that can be targets of
  hyperlinks

.. autoclass:: Href
   :members:

.. autoclass:: Referrable
   :members:

Pydantic models
---------------

Any `pydantic <https://pydantic-docs.helpmanual.io/>`_ model that is a target of
hyperlinks should implement :class:`BaseReferrableModel`. It inherits both
:class:`pydantic.BaseModel` and :class:`hrefs.Referrable`.

.. autoclass:: BaseReferrableModel
   :members:

.. autoclass:: PrimaryKey

.. autoclass:: HrefsConfigDict
   :members:

Starlette integration
---------------------

.. module:: hrefs.starlette

The main motivation for writing this library was to make it easy to use
hyperlinks in `FastAPI <https://fastapi.tiangolo.com/>`_ and `Starlette
<https://www.starlette.io/>`_ applications. See :ref:`quickstart` for a fully
working example of how to use these classes.

.. autoclass:: HrefMiddleware

.. autofunction:: href_context

.. _custom_web_framework_api:

Custom web framework integrations
---------------------------------

Developers of custom web framework integrations that work with
:class:`BaseReferrableModel` need to implement a hyperlink resolver that acts as
a bridge between the ``hrefs`` library and the framework.

The implementation of :mod:`hrefs.starlette` can be used as a reference.

.. autoclass:: hrefs.model.HrefResolver
   :members:

.. autofunction:: hrefs.model.resolve_hrefs

Exceptions
----------

.. autoexception:: hrefs.ReferrableModelError
