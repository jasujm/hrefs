Hyperlinks for pydantic models
==============================

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

   class Book(ReferrableModel):
       id: int

       class Config:
           details_view = "get_book"

   class Library(BaseModel):
       books: List[Href[Book]]

   @app.get("/library")
   def get_library():
       # Will produce something like:
       # {"books":["http://example.com/books/1","http://example.com/books/2","http://example.com/books/3"]}
       return Library(books=[1,2,3]).json()

``hrefs`` was written especially with `FastAPI <https://fastapi.tiangolo.com/>`_
in mind, but integrates into any application or framework using pydantic to
parse and serialize models.

Check out the `documentation <https://hrefs.readthedocs.io/>`_ to get started!

Installation
------------

Install the library using ``pip`` or your favorite package management tool:

.. code-block:: console

   $ pip install hrefs
