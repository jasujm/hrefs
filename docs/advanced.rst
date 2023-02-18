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
   def get_page(book_id: int, page_number: int):
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

       class Config:
           details_view = "get_book"

   class Page(ReferrableModel):
       book: Annotated[Href[Book], PrimaryKey]
       page_number: Annotated[int, PrimaryKey]

       class Config:
           details_view = "get_page"

   @app.get("/books/{id}", response_model=Book)
   def get_book(id: int):
       # implementation

   @app.get("/books/{book_id}/pages/{page_number}", response_model=Book)
   def get_page(book_id: int, page_number: int):
       # implementation

Note that the path parameter in the ``get_page`` route handler is called
``book_id``, which is simply the hyperlink name ``book`` joined to ``id`` -- the
model key of ``Book``. This is because FastAPI doesn't know how to convert
to/from custom types like ``Href`` in path parameters. So the key type is
automatically unwrapped and renamed when it appears in route handler. In the
model itself the name and type of ``book`` are preserved:

.. code-block:: python

   print(Page(book=1, page_number=123))
   # will produce something like:
   book=Href(key=1, url="http://example.com/api/books/1") page_number=1

.. _self_hrefs:

Self hyperlinks
---------------

It is possible to have a hyperlink to the model itself as a primary
key. Expanding the idea in :ref:`href_as_key`, we can have:

.. code-block:: python

   from typing import Annotated
   from hrefs import Href, PrimaryKey
   from hrefs.starlette import ReferrableModel

   class Book(ReferrableModel):
       self: Annotated[Href["Book"], PrimaryKey(type_=int, name="id")]

       class Config:
           details_view = "get_book"

   Book.update_forward_refs()

   @app.get("/books/{id}", response_model=Book)
   def get_book(id: int):
       # implementation

Note the need to use forward reference ``"Book"`` inside the body of the class,
and update the forward references afterward. That is because the name ``Book``
is not yet available in the class body. Also the ``PrimaryKey`` annotation now
includes the ``type_`` argument to indicate that the underlying key type is
``int``. Without that annotation, the library would have no way of knowing the
underlying key of the model, since the definition of the primary key would be
circular.

Note that the key name in the route handler is again unwrapped -- and called
``id`` instead of ``self``. This is because the ``name`` argument of the
``PrimaryKey`` annotation was used to rename a key. It is not advisable to have
``self`` as an argument name in a route handler, because it creates ambiguity
with the ``self`` parameter Python uses in instance methods.

The unwrapping only applies to the route handler. In the model itself the name
and type of ``self`` are preserved:

.. code-block:: python

   print(Book(self=1))
   # will produce something like:
   self=Href(key=1, url="http://example.com/api/books/1")

Having both ``id`` and ``self``
...............................

It is possible to have ``self`` hyperlink without it being a primary key. A
common pattern in APIs is to include both ``id`` primary key and the ``self``
hyperlink. A recipe to achieve that is:

.. code-block:: python

   from hrefs import Href
   from hrefs.starlette import ReferrableModel
   from pydantic import root_validator

   class Book(ReferrableModel):
       id: int
       self: Href["Book"]

       @root_validator(pre=True)
       def populate_self(cls, values):
           values["self"] = values["id"]
           return values

   Book.update_forward_refs()

   book = Book(id=123)
   # book.self is automatically populated from id

Note that ``id`` will become the primary key by the virtue of being called
``id``. In the example above, ``self`` is just a regular field that happens to
be a hyperlink to the ``Book`` model itself. The ``Book.populate_self()`` runs
on the whole model before any other validation takes place, and takes care of
populating the ``self`` field from ``id``.

The ``PrimaryKey`` annotation with type is no longer needed since there is
nothing circular in the key type (compare this to :ref:`self_hrefs`).

Inheritance
-----------

It is possible for a referrable model to inherit another:

.. code-block:: python

   class Book(ReferrableModel):
       id: int
       title: str

       class Config:
           details_view = "get_book"

   class Textbook(Book):
       subject: str

The derived model ``Textbook`` inherits the key ``id`` and details view
``"get_book"`` from its parent ``Book``.

Primary key annotations are not composable across inheritance, i.e. it is not
possible to define a part of the model key in the parent and another part in the
derived model. Model key definitions --- whether implicit or explicit --- should
only exist in one class of the inheritance tree.
