.. _api:

API reference
=============

.. module:: hrefs

Fundamentals
------------

The two main building blocks of the :mod:`hrefs` library are

* :class:`Href`, the class representing hyperlinks

* :class:`Referrable`, the protocol/ABC of types that can be targets of
  hyperlinks

.. autoclass:: Href
   :members:

.. autoclass:: Referrable
   :members:

   .. automethod:: __modify_href_schema__

Pydantic models
---------------

Any `pydantic <https://pydantic-docs.helpmanual.io/>`_ model that is a target of
hyperlinks should implement :class:`BaseReferrableModel`. It inherits both
:class:`pydantic.BaseModel` and :class:`hrefs.Referrable`.

.. autoclass:: BaseReferrableModel
   :members:

.. autoclass:: PrimaryKey

Starlette integration
---------------------

.. module:: hrefs.starlette

The main motivation for writing the library was to make it easy to use
hyperlinks in `FastAPI <https://fastapi.tiangolo.com/>`_ and `Starlette
<https://www.starlette.io/>`_ applications. See :ref:`quickstart` for a fully
working example of how to use these classes.

.. autoclass:: ReferrableModel

.. autoclass:: HrefMiddleware

.. autofunction:: href_context
