.. _quickstart:

Getting started
===============

Using ``hrefs`` with FastAPI
----------------------------

Setting up the application
..........................

The :mod:`hrefs` library resolves URLs automatically. For that to work, it only
needs the :class:`hrefs.starlette.HrefMiddleware` to be included in the
middleware stack:

.. code-block:: python

   from fastapi import FastAPI
   from fastapi.middleware import Middleware
   from hrefs.starlette import HrefMiddleware

   app = FastAPI(middleware=[Middleware(HrefMiddleware)])

.. _starlette_models:

Defining a referrable model
...........................

.. code-block:: python

   from hrefs.starlette import ReferrableModel

   class Book(ReferrableModel):
       id: int
       title: str

       class Config:
           details_view = "get_book"

   @app.get("/books/{id}", response_model=Book)
   def get_book(id: int):
       book = books.get(id)
       if not book:
           raise HTTPException(status_code=404, detail="Book not found")
       return book

To make a model target for hrefs, it needs to:

* Inherit from :class:`hrefs.starlette.ReferrableModel`.

* Have a configuration called ``details_view`` naming the route that will return
  the details of the referrable model. The URLs will be built by reversed
  routing, using the *primary key* of the model as parameters.

* Have a primary key used as a router parameter in ``details_view``. In the
  above example ``Book.id`` is the primary key. This may or may not correspond
  to the primary key in a database, but ``hrefs`` really isn't concerned the
  database layer. By default, the primary key is the ``id`` field but can be
  configured. See :ref:`configure_key` for details.

.. note::

   If the way to set up the route doesn't look familiar, refer to the `FastAPI
   <https://fastapi.tiangolo.com/>`_ documentation. The route name defaults to
   the name of the handler function, but can also be defined explicitly using
   the ``name`` keyword argument in the ``@app.get()`` decorator.

Defining a relationship to the referrable model
...............................................

.. code-block:: python

   from fastapi import HTTPException, Request, Response
   from hrefs import Href
   from pydantic import BaseModel

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
   def post_library(library: Library, request: Request):
       if any(book.get_key() not in books for book in library.books):
           raise HTTPException(
               status_code=400, detail="Trying to add a nonexistent book to library"
           )
       libraries[library.id] = library
       return Response(
           status_code=201,
           headers={"Location": request.url_for("get_library", id=library.id)},
       )

An annotated type ``Href[Book]`` is used to declare a hyperlink to ``Book`` ---
or any other subclass of :class:`hrefs.Referrable` for that matter!

The :class:`hrefs.Href` class integrates to `pydantic
<https://pydantic-docs.helpmanual.io/>`_. When parsing the ``books`` field, the
following values can automatically be converted to hrefs:

* Another :class:`hrefs.Href` instance.

* An instance of the referred object type (in this case ``Book``).

* A value convertible to the ``id`` type of the referred object (in this case
  ``int``).

* A URL that can be matched to the route named in the ``details_view`` of the
  referred object type (in this case ``"get_library"``).

When ``pydantic`` serializes :class:`hrefs.Href` objects to JSON, it is
represented by URL.

A full working example
......................

The ``tests/`` folder contains a minimal toy application demonstrating how the
:mod:`hrefs` library is used. The code is reproduced here for convenience:

.. literalinclude:: ../tests/app.py
   :language: python

You can run the test application on your favorite ASGI server:

.. code-block:: console

   $ uvicorn tests.app:app
   INFO:     Started server process
   INFO:     Waiting for application startup.
   INFO:     Application startup complete.
   INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)

Then use your favorite HTTP client and start creating libraries. You can use
either IDs or URLs to refer to the books in the second ``POST`` request --- the
library knows how to parse either!

.. code-block:: console

   $ http POST localhost:8000/books title='My first book'
   HTTP/1.1 201 Created
   Transfer-Encoding: chunked
   location: http://localhost:8000/books/fb69a5d5-b956-4189-8e3e-89f001815bec
   server: uvicorn


   $ http POST localhost:8000/libraries books:='["http://localhost:8000/books/fb69a5d5-b956-4189-8e3e-89f001815bec"]'
   HTTP/1.1 201 Created
   Transfer-Encoding: chunked
   location: http://localhost:8000/libraries/50c224ff-c9f4-4186-8a05-4999f522ea67
   server: uvicorn


   $ http GET http://localhost:8000/libraries/50c224ff-c9f4-4186-8a05-4999f522ea67
   HTTP/1.1 200 OK
   content-length: 50
   content-type: application/json
   server: uvicorn

   {
       "books": [
           "http://localhost:8000/books/fb69a5d5-b956-4189-8e3e-89f001815bec"
       ],
       "self": "http://localhost:8000/libraries/50c224ff-c9f4-4186-8a05-4999f522ea67"
   }

Using ``hrefs`` with Starlette
------------------------------

While the library was written with `FastAPI <https://fastapi.tiangolo.com/>`_ in
mind, the integration doesn't depend on FastAPI, only `pydantic
<https://pydantic-docs.helpmanual.io/>`_ and `Starlette
<https://www.starlette.io/>`_. You can perfectly well write Starlette apps
containing hrefs. You just need to ensure that:

* For each subclass of :class:`hrefs.starlette.ReferrableModel` there is a named
  route matching the ``details_view`` configuration.

* :class:`hrefs.starlette.HrefMiddleware` is added to the middleware stack.

* In the responses, the pydantic models containing references are explicitly
  serialized using ``model.json()`` method.

Writing a custom integration
----------------------------

The :class:`hrefs.Href` class can refer to any type implementing the
:class:`hrefs.Referrable` protocol. You can also use the
:class:`hrefs.BaseReferrableModel` ABC to get part of the implementation for
free.
