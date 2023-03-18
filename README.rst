Hyperlinks for pydantic models
==============================

Read `a blog post from the library author
<https://www.jmoisio.eu/en/blog/2023/03/12/a-library-for-managing-hyperlinks-in-modern-python-web-applications/>`_
discussing why this library exists.

In a typical web application relationships between resources are modeled by
primary and foreign keys in a database (integers, UUIDs, etc.). The most natural
way to represent relationships in REST APIs is by URLs to the related resources
(explained in `this blog
<https://cloud.google.com/blog/products/application-development/api-design-why-you-should-use-links-not-keys-to-represent-relationships-in-apis>`_).

``hrefs`` makes it easy to add hyperlinks between `pydantic
<https://pydantic-docs.helpmanual.io/>`_ models in a declarative way. Just
declare a ``Href`` field and the library will automatically convert between keys
and URLs:

.. code-block:: python

   from hrefs import Href, BaseReferrableModel
   from pydantic import BaseModel

   class Book(BaseReferrableModel):
       id: int

       class Config:
           details_view = "get_book"

   class Library(BaseModel):
       books: list[Href[Book]]

   @app.get("/books/{id}")
   def get_book(id: int) -> Book:
       return Book(id=id)

   @app.get("/library")
   def get_library() -> Library:
       """
       Will serialize into:
       {"books":["https://example.com/books/1","https://example.com/books/2","https://example.com/books/3"]}
       """
       return Library(books=[1,2,3])

   @app.post("/library")
   def post_library(library: Library):
       """
       Assuming the request contains
       {"books":["https://example.com/books/1","https://example.com/books/2","https://example.com/books/3"]}
       Will deserialize into: [1,2,3]
       """
       write_to_database([href.key for href in library.books])

``hrefs`` was written especially with `FastAPI <https://fastapi.tiangolo.com/>`_
in mind, but integrates into any application or framework using pydantic to
parse and serialize models.

Check out the `documentation <https://hrefs.readthedocs.io/>`_ to get started!

Installation
------------

Install the library using ``pip`` or your favorite package management tool:

.. code-block:: console

   $ pip install hrefs
