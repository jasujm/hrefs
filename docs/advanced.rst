.. _advanced:

Advanced topics
===============

.. _configure_key:

Configuring model key
---------------------

By default, the primary key of a model inheriting from
:class:`hrefs.BaseReferrableModel` (or, by extension,
:class:`hrefs.starlette.ReferrableModel`) is called ``id``. This can be changed
by annotating another field with :class:`hrefs.PrimaryKey`.

.. code-block:: python

   from typing import Annotation
   from hrefs import BaseReferrableModel, PrimaryKey

   class MyModel(BaseReferrableModel):
       my_id: Annotated[int, PrimaryKey]

       # ...the rest of the definitions...

Then ``MyModel.my_id`` is the key used by ``Href[MyModel]``.

.. note::

   Before Python 3.8, ``typing_extensions.Annotation`` can be used to annotate
   the fields.

Composite keys
..............

It is also possible to annotate multiple fields with ``PrimaryKey``. It will
cause the primary key to be a named tuple of the annotated fields:

.. code-block:: python

   from typing import Annotation
   from hrefs import BaseReferrableModel, PrimaryKey

   class Page(BaseReferrableModel):
       book_id: Annotated[int, PrimaryKey]
       page_number: Annotated[int, PrimaryKey]

       # ...the rest of the definition...

When using composite keys with :ref:`FastAPI or Starlette models
<starlette_models>`, each part of the key must appear in the route template.


.. code-block:: python

   from typing import Annotation
   from hrefs import PrimaryKey
   from hrefs.starlette import ReferrableModel

   class Page(ReferrableModel):
       book_id: Annotated[int, PrimaryKey]
       page_number: Annotated[int, PrimaryKey]

       class Config:
           details_view = "get_page"

   @app.get("/books/{book_id}/pages/{page_number}", response_model=Page)
   def get_book(id: int):
       # implementation
