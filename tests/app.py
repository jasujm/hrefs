"""A test application

This is a self-contained demo of the `hrefs` library. You can run it with your
favorite ASGI server, and interact with it using your favorite HTTP client.

Its state is only contained in memory, so it is advisable also to manage your
libraries in a more persistent format!
"""

# pylint: disable=wrong-import-position,wrong-import-order

from typing import Dict, List
import uuid

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware import Middleware
from pydantic import BaseModel, parse_obj_as
from typing_extensions import Annotated

from hrefs import Href, PrimaryKey
from hrefs.starlette import ReferrableModel, HrefMiddleware


class _BookBase(BaseModel):
    title: str


class BookCreate(_BookBase):
    """Book creation payload"""


class Book(ReferrableModel, _BookBase):
    """Book in a library

    A book has a `title` and identity, represented by a hyperlink in the `self`
    field.
    """

    self: Annotated[Href["Book"], PrimaryKey(type_=uuid.UUID, name="id")]

    class Config:
        """Book config

        The `hrefs` library requires `details_view` option, which is the name of
        the Starlette route (in this case FastAPI route that is a Starlette
        route under the hood) serving the representation of a book.
        """

        details_view = "get_book"


Book.update_forward_refs()


class _LibraryBase(BaseModel):
    books: List[Href[Book]]


class LibraryCreate(_LibraryBase):
    """Library creation payload"""


class Library(ReferrableModel, _LibraryBase):
    """A library containing some books

    A library has a list of `books`, represented by hyperlinks. Its own identity
    in `self` is also a hyperlink.
    """

    self: Annotated[Href["Library"], PrimaryKey(type_=uuid.UUID, name="id")]

    class Config:
        """Book config

        The `hrefs` library requires `details_view` option, which is the name of
        the Starlette route (in this case FastAPI route that is a Starlette
        route under the hood) serving the representation of a library.
        """

        details_view = "get_library"


Library.update_forward_refs()

books: Dict[Href[Book], Book] = {}
libraries: Dict[Href[Library], Library] = {}

app = FastAPI(middleware=[Middleware(HrefMiddleware)])


@app.get("/libraries/{id}", response_model=Library)
def get_library(id: uuid.UUID):
    """Retrieve a library identified by `id`"""
    href = parse_obj_as(Href[Library], id)
    library = libraries.get(href)
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")
    return library


@app.post("/libraries")
def post_library(library: LibraryCreate):
    """Create a new library

    A library can contain any number of books, represented by a list of
    hyperlinks. The books can either be referred by their `id` (an UUID encoded
    as a string), or a hyperlink (an URL previously returned by `POST /books`
    call).

    The identity will be automatically generated, and returned in the `Location`
    header.

    """
    if any(book not in books for book in library.books):
        raise HTTPException(
            status_code=400, detail="Trying to add nonexisting book to library"
        )
    new_library = Library(self=uuid.uuid4(), **library.dict())
    libraries[new_library.self] = new_library
    return Response(
        status_code=201,
        headers={"Location": new_library.self.url},
    )


@app.get("/books/{id}", response_model=Book)
def get_book(id: uuid.UUID):
    """Retrieve a book identified by `id`"""
    href = parse_obj_as(Href[Book], id)
    book = books.get(href)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@app.post("/books", status_code=204)
def post_book(book: BookCreate):
    """Create a new book

    The identity will be automatically generated, and returned in the `Location`
    header."""
    new_book = Book(self=uuid.uuid4(), **book.dict())
    books[new_book.self] = new_book
    return Response(status_code=201, headers={"Location": new_book.self.url})
