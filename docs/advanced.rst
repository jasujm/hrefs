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

   from typing import Annotated
   from hrefs import BaseReferrableModel, PrimaryKey

   class MyModel(BaseReferrableModel):
       my_id: Annotated[int, PrimaryKey]

       # ...the rest of the definitions...

Then ``MyModel.my_id`` is the key used by ``Href[MyModel]``.

.. note::

   Before Python 3.8, ``typing_extensions.Annotated`` can be used to annotate
   the fields.

Composite keys
..............

It is also possible to annotate multiple fields with ``PrimaryKey``. It will
cause the primary key to be a named tuple of the annotated fields:

.. code-block:: python

   from typing import Annotated
   from hrefs import BaseReferrableModel, PrimaryKey

   class Page(BaseReferrableModel):
       book_id: Annotated[int, PrimaryKey]
       page_number: Annotated[int, PrimaryKey]

       # ...the rest of the definition...

When using composite keys with :ref:`FastAPI or Starlette models
<starlette_models>`, each part of the key must appear in the route template.


.. code-block:: python

   from typing import Annotated
   from hrefs import PrimaryKey
   from hrefs.starlette import ReferrableModel

   class Page(ReferrableModel):
       book_id: Annotated[int, PrimaryKey]
       page_number: Annotated[int, PrimaryKey]

       class Config:
           details_view = "get_page"

   @app.get("/books/{book_id}/pages/{page_number}", response_model=Page)
   def get_page(id: int):
       # implementation

.. _href_as_key:

Hyperlinks as keys
..................

A model can also have a :class:`hrefs.Href` object as (a part of) its model key.
Modifying the example from the previous section we have:


.. code-block:: python

   from typing import Annotated
   from hrefs import Href, PrimaryKey
   from hrefs.starlette import ReferrableModel

   class Book(ReferrableModel):
       id: int

   class Page(ReferrableModel):
       book: Annotated[Href[Book], PrimaryKey]
       page_number: Annotated[int, PrimaryKey]

       class Config:
           details_view = "get_page"

   @app.get("/books/{id}", response_model=Book)
   def get_book(id: int):
       # implementation

   @app.get("/books/{book}/pages/{page_number}", response_model=Book)
   def get_page(book: int, page_number: int):
       # implementation

Note how the type of the ``book`` parameter is ``int`` rather than
``Href[Book]`` in the signature of ``get_page``. This is because FastAPI doesn't
know how to convert to/from non-elementary like ``Href`` in path parameters. So
the key is automatically unwrapped in the router. That is not true for the
models themselves, however:

.. code-block:: python

   print(Page(book=1, page_number=123))
   # will produce something like:
   book=Href(key=1, url="http://example.com/api/books/1") page_number=1

Self references
...............

.. warning::

   **WIP!** This doesn't actually work yet. There is name conflict with the
   ``self`` being used as path parameter *and* the ``self`` argument for
   methods.

It is even possible to have hyperlink to the model itself as a primary key:

.. code-block:: python

   from typing import Annotated, ForwardRef
   from hrefs import Href, PrimaryKey
   from hrefs.starlette import ReferrableModel

   class Book(ReferrableModel):
       self: Annotated[Href[ForwardRef("Book")], PrimaryKey(type_=int)]

   Book.update_forward_refs()

   @app.get("/books/{self}", response_model=Book)
   def get_book(self: int):
       # implementation

Note the need to use ``ForwardRef("Book")`` inside the body of the class, and
updating the forward references afterward. Also the ``PrimaryKey`` annotation
now includes the ``type_`` argument to indicate that the underlying key type is
``int``. Without that annotation the library would have no way of knowing the
underlying key of the model, since the definition of the primary key would be
circular.

The ``self`` parameter in the route handler is again unwrapped (see
:ref:`href_as_key`), but the ``self`` field of a parsed model is still a
hyperlink:

.. code-block:: python

   print(Book(self=1))
   # will produce something like:
   self=Href(key=1, url="http://example.com/api/books/1")
