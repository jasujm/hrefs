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

Pydantic models
---------------

The library provides two mixins that make writing `pydantic
<https://pydantic-docs.helpmanual.io/>`_ models using :mod:`hrefs`
easier. Generally any model using :class:`Href` fields should be a subclass of
:class:`BaseModel`. Any model that is also a target of hyperlinks should
implement :class:`BaseReferrableModel`. :class:`BaseReferrableModel` is also a
subclass of :class:`BaseModel`, so no need to inherit both!

.. autoclass:: BaseModel

.. autoclass:: BaseReferrableModel

Starlette integration
---------------------

.. module:: hrefs.starlette

The main motivation for writing the library was to make it easy to use
hyperlinks in `FastAPI <https://fastapi.tiangolo.com/>`_ and `Starlette
<https://www.starlette.io/>`_ applications. See :ref:`quickstart` for a full
working example how to use these classes.

.. autoclass:: HrefMiddleware

.. autoclass:: ReferrableModel
