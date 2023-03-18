.. testsetup:: *

   from fastapi import FastAPI
   from fastapi.middleware import Middleware
   from hrefs.starlette import HrefMiddleware, href_context

   app = FastAPI(middleware=[Middleware(HrefMiddleware)])
   context = href_context(app, base_url="http://example.com")
   context.__enter__()

.. testcleanup:: *

   context.__exit__(None, None, None)

.. _advanced:

Advanced topics
===============

.. _configure_key:

Configuring model key
---------------------

By default, the primary key of a model inheriting from
:class:`hrefs.BaseReferrableModel` is called ``id``. This can be changed by
annotating another field with :class:`hrefs.PrimaryKey`.

.. testcode:: primary_key_annotation

   from typing import Annotated
   from hrefs import Href, BaseReferrableModel, PrimaryKey
   from pydantic import parse_obj_as

   class MyModel(BaseReferrableModel):
       my_id: Annotated[int, PrimaryKey]

       class Config:
           details_view = "get_my_model"

   @app.get("/my_models/{my_id}")
   def get_my_model(my_id: int) -> MyModel:
       ...

Then ``MyModel.my_id`` is the key used by ``Href[MyModel]``.

.. doctest:: primary_key_annotation

   >>> model = MyModel(my_id=1)
   >>> model.get_key()
   1
   >>> parse_obj_as(Href[MyModel], model)
   Href(key=1, url=AnyHttpUrl(...'http://example.com/my_models/1'...))

.. note::

   Before Python 3.8, ``typing_extensions.Annotated`` can be used to annotate
   the fields.

Composite keys
..............

It is also possible to annotate multiple fields with ``PrimaryKey``. When using
composite keys with :ref:`FastAPI or Starlette models <starlette_models>`, each
part of the key must appear in the route template.

.. testcode:: composite_key

   from typing import Annotated
   from hrefs import Href, BaseReferrableModel, PrimaryKey
   from pydantic import parse_obj_as

   class Page(BaseReferrableModel):
       book_id: Annotated[int, PrimaryKey]
       page_number: Annotated[int, PrimaryKey]

       class Config:
           details_view = "get_page"

   @app.get("/books/{book_id}/pages/{page_number}")
   def get_page(book_id: int, page_number: int) -> Page:
       ...

The primary key of the model will be a named tuple of the annotated parts.

.. doctest:: composite_key

   >>> page = Page(book_id=1, page_number=123)
   >>> page.get_key()
   key(book_id=1, page_number=123)
   >>> parse_obj_as(Href[Page], page)
   Href(key=key(book_id=1, page_number=123), url=AnyHttpUrl(...'http://example.com/books/1/pages/123'...))

.. _href_as_key:

Hyperlinks as keys
..................

A model can also have a :class:`hrefs.Href` object as (a part of) its model key.
Modifying the example from the previous section we have:

.. testcode:: href_as_key

   from typing import Annotated
   from hrefs import Href, BaseReferrableModel, PrimaryKey
   from pydantic import parse_obj_as

   class Book(BaseReferrableModel):
       id: int

       class Config:
           details_view = "get_book"

   class Page(BaseReferrableModel):
       book: Annotated[Href[Book], PrimaryKey]
       page_number: Annotated[int, PrimaryKey]

       class Config:
           details_view = "get_page"

   @app.get("/books/{id}")
   def get_book(id: int) -> Book:
       ...

   @app.get("/books/{book_id}/pages/{page_number}")
   def get_page(book_id: int, page_number: int) -> Page:
       ...

Note that the path parameter in the ``get_page`` route handler is called
``book_id``, which is simply the hyperlink name ``book`` joined to ``id`` -- the
model key of ``Book``. This is because FastAPI doesn't know how to convert
to/from custom types like ``Href`` in path parameters. The key type is
automatically unwrapped and renamed when it appears in route handler. In the
model itself the name and type of ``book`` are preserved:

.. doctest:: href_as_key

   >>> page = Page(book=1, page_number=123)
   >>> page.get_key()
   key(book=Href(key=1, url=AnyHttpUrl(...'http://example.com/books/1'...)), page_number=123)
   >>> href = parse_obj_as(Href[Page], page)
   >>> href.key
   key(book=Href(key=1, url=AnyHttpUrl(...'http://example.com/books/1'...)), page_number=123)
   >>> href.url
   AnyHttpUrl(...'http://example.com/books/1/pages/123'...)

.. _self_hrefs:

Self hyperlinks
---------------

It is possible to have a hyperlink to the model itself as a primary
key. Expanding the idea in :ref:`href_as_key`, we can have:

.. testcode:: self_hrefs

   from typing import Annotated
   from hrefs import Href, BaseReferrableModel, PrimaryKey
   from pydantic import parse_obj_as

   class Book(BaseReferrableModel):
       self: Annotated[Href["Book"], PrimaryKey(type_=int, name="id")]

       class Config:
           details_view = "get_book"

   Book.update_forward_refs()

   @app.get("/books/{id}")
   def get_book(id: int) -> Book:
       ...

Note the need to use forward reference ``"Book"`` inside the body of the class,
and update the forward references afterward. That is because the name ``Book``
is not yet available in the class body. Also the ``PrimaryKey`` annotation now
includes the ``type_`` argument to indicate that the underlying key type is
``int``. Without that annotation, the library would have no way of knowing the
underlying key of the model, since the definition of the primary key would be
circular.

The key name in the route handler is again unwrapped -- and called ``id``
instead of ``self``. This is because the ``name`` argument of the ``PrimaryKey``
annotation was used to rename a key. It is not advisable to have ``self`` as an
argument name in a route handler, because it creates ambiguity with the ``self``
parameter Python uses in instance methods.

The unwrapping only applies to the route handler. In the model itself the name
and type of ``self`` are preserved:

.. doctest:: self_hrefs

   >>> book = Book(self=1)
   >>> book.get_key()
   1
   >>> book
   Book(self=Href(key=1, url=AnyHttpUrl(...'http://example.com/books/1'...)))
   >>> parse_obj_as(Href[Book], book)
   Href(key=1, url=AnyHttpUrl(...'http://example.com/books/1'...))

Having both ``id`` and ``self``
...............................

It is possible to have ``self`` hyperlink without it being a primary key. A
common pattern in APIs is to include both ``id`` primary key and the ``self``
hyperlink. A recipe to achieve that is:

.. testcode:: id_and_self

   from hrefs import Href, BaseReferrableModel
   from pydantic import root_validator, parse_obj_as

   class Book(BaseReferrableModel):
       id: int
       self: Href["Book"]

       @root_validator(pre=True, allow_reuse=True)
       def populate_self(cls, values):
           values["self"] = values["id"]
           return values

       class Config:
           details_view = "get_book"

   Book.update_forward_refs()

   @app.get("/books/{id}")
   def get_book(id: int) -> Book:
       ...

.. note::

   You may need to add ``allow_reuse=True`` as an argument to
   ``@root_validator`` to make the above code work. There is an `open issue
   <https://github.com/jasujm/hrefs/issues/8>`_ to investigate why and if it's
   really needed.

In the above example, ``id`` will become the primary key by the virtue of being
called ``id``. In the example above, ``self`` is just a regular field that
happens to be a hyperlink to the ``Book`` model itself. The
``Book.populate_self()`` runs on the whole model before any other validation
takes place, and takes care of populating the ``self`` field from ``id``.

.. doctest:: id_and_self

   >>> book = Book(id=1)
   >>> book
   Book(id=1, self=Href(key=1, url=AnyHttpUrl(...'http://example.com/books/1'...)))

The ``PrimaryKey`` annotation with type is no longer needed since there is
nothing circular in the key type (compare this to :ref:`self_hrefs`).

Inheritance
-----------

It is possible for a referrable model to inherit another:

.. testcode:: inheritance

   from hrefs import Href, BaseReferrableModel
   from pydantic import parse_obj_as

   class Book(BaseReferrableModel):
       id: int
       title: str

   class Textbook(Book):
       subject: str

       class Config:
           details_view = "get_textbook"

   @app.get("/textbooks/{id}")
   def get_textbook(id: int) -> Textbook:
       ...

The derived model ``Textbook`` inherits the key ``id`` and details view
``"get_book"`` from its parent ``Book``.

.. doctest:: inheritance

   >>> textbook = Textbook(id=1, title="Introduction to hrefs", subject="hrefs")
   >>> textbook.get_key()
   1
   >>> parse_obj_as(Href[Textbook], textbook)
   Href(key=1, url=AnyHttpUrl(...'http://example.com/textbooks/1'...))

Primary key annotations are not composable across inheritance, i.e. it is not
possible to define a part of the model key in the parent and another part in the
derived model. Model key definitions --- whether implicit or explicit --- should
only exist in one class of the inheritance tree.
