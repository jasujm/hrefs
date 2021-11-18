.. _quickstart:

Getting started
===============

Using ``hrefs`` with FastAPI
----------------------------

Setting up the application
..........................

The :mod:`hrefs` library resolves URLs automatically. In order for that to work,
it only needs the :class:`hrefs.HrefMiddleware` to be included in the middleware
stack:

.. code-block:: python

   from fastapi import FastAPI
   from fastapi.middleware import Middleware
   from hrefs.starlette import HrefMiddleware

   app = FastAPI(middleware=[Middleware(HrefMiddleware)])

Defining a referrable model
...........................

.. code-block:: python

   from hrefs.starlette import ReferrableModel

   class Book(ReferrableModel):
       id: int
       title: str

       class Config:
           default_view = "get_book"

   @app.get("/books/{id}", response_model=Book)
   def get_book(id: int):
       book = books.get(id)
       if not book:
           raise HTTPException(status_code=404, detail="Book not found")
       return book

To make a model target for hrefs, it needs to:

* Inherit from :class:`hrefs.starlette.ReferrableModel`.

* Have configuration called ``default_view`` naming the route that will return
  the canonical representation of the referrable model. The URLs will be derived
  from the path of that view plus the identity of the model.

.. note::

   If the way to set up the route doesn't look familiar, refer to the `FastAPI
   <https://fastapi.tiangolo.com/>`_ documentation. The route name defaults to
   the name of the handler function, but can also be defined explicitly using
   the ``name`` keyword argument in the ``@app.get()`` decorator.

.. note::

   Currently it is assumed that **both** the primary key of the model, and the
   path parameter of the route, are called ``id``. It will be customizable in
   later version of the library.

Defining a relationship to the referrable model
...............................................

.. code-block:: python

   from fastapi import HTTPException, Request, Response
   from hrefs import BaseModel, Href

   class Library(BaseModel):
       id: int
       books: List[Href[Book]]

   @app.get("/libraries/{id}", response_model=Library)
   def get_library(id: int):
       library = libraries.get(id)
       if not library:
           raise HTTPException(status_code=404, detail="Library not found")
       return library

   @app.post("/libraries")
   def post_library(library: Library, request: Request, response: Response):
       if any(book.get_key() not in books for book in library.books):
           raise HTTPException(
               status_code=400, detail="Trying to add nonexisting book to library"
           )
       libraries[library.id] = library
       response.headers["Location"] = request.url_for("get_library", id=library.id)

.. note::

   The ``Library`` model derives from :class:`hrefs.BaseModel`, and not
   ``pydantic.BaseModel``. The difference is that :class:`hrefs.BaseModel` is
   configures to use a custom JSON encoder that knows how to handle
   :class:`hrefs.Href` objects.

An annotated type ``Href[Book]`` is used to declare a hypertext reference to
``Book`` --- or any other subclass of :class:`hrefs.ReferrableModel` for that
matter!

The :class:`hrefs.Href` class integrates to `pydantic
<https://pydantic-docs.helpmanual.io/>`_. When parsing the ``books`` field (or
any other ), the following values can automatically be converted to `Href`
instances:

* Another :class:`hrefs.Href` instance.

* An instance of the referred object type (in this case ``Book``).

* A value convertible to the ``id`` type of the referred object (in this case
  ``int``).

* A URL that can be matched to the route named in the ``default_view`` of the
  referred object type (in this case ``"get_library"``).

When serializing :class:`hrefs.Href` objects to JSON (FastAPI serializes the
object returned from the route handler behind the scenes!), it will be
represented by URL.

A full working example
......................

The ``tests/`` folder contains a minimal toy application demonstrating how the
:mod:`hrefs` library is used. The code is reproduced here for convenience:

.. literalinclude:: ../tests/app.py
   :language: python

You can run the test application in your favorite ASGI server:

.. code-block:: console

   $ uvicorn tests.app:app
   INFO:     Started server process
   INFO:     Waiting for application startup.
   INFO:     Application startup complete.
   INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)

Then use your favorite HTTP client and start creating libraries. You can use
either IDs or URL to refer to the books in the second ``POST`` request --- the
library knows how to parse either!

.. code-block:: console

   $ http POST localhost:8000/books id=1 title='My first book'
   HTTP/1.1 201 Created
   Transfer-Encoding: chunked
   location: http://localhost:8000/books/1
   server: uvicorn


   $ http POST localhost:8000/libraries id=1 books:='["http://localhost:8000/books/1"]'
   HTTP/1.1 201 Created
   Transfer-Encoding: chunked
   location: http://localhost:8000/libraries/1
   server: uvicorn


   $ http GET http://localhost:8000/libraries/1
   HTTP/1.1 200 OK
   content-length: 50
   content-type: application/json
   server: uvicorn

   {
       "books": [
           "http://localhost:8000/books/1"
       ],
       "id": 1
   }

Using ``hrefs`` with Starlette
------------------------------

While the library was written with `FastAPI <https://fastapi.tiangolo.com/>`_ in
mind, the integration doesn't actually depend on FastAPI, only `pydantic
<https://pydantic-docs.helpmanual.io/>`_ and `Starlette
<https://www.starlette.io/>`_. You can perfectly well write Starlette apps
containing hrefs. You just need to ensure that:

* For each :class:`hrefs.starlette.ReferrableModel` there is a named
  route matching the ``default_view`` configuration.

* The :class:`HrefMiddleware` is added as middleware to the application.

* In the responses, the pydantic models containing references are explicitly
  serialized using ``model.json()`` method.

Writing a custom integration
----------------------------

The :class:`hrefs.Href` class can refer to any type implementing the
:class:`hrefs.Referrable` protocol. You can also use the
:class:`hrefs.BaseReferrableModel` ABC to get part of the implementation for
free.
