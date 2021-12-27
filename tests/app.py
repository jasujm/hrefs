from typing import List, Dict, ForwardRef
import uuid

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware import Middleware
from pydantic import BaseModel
from typing_extensions import Annotated

from hrefs import Href, PrimaryKey
from hrefs.starlette import ReferrableModel, HrefMiddleware


class BookCreate(BaseModel):
    title: str


class Book(ReferrableModel):
    self: Annotated[Href[ForwardRef("Book")], PrimaryKey(type_=uuid.UUID, name="id")]
    title: str

    class Config:
        details_view = "get_book"


Book.update_forward_refs()


class LibraryCreate(BaseModel):
    books: List[Href[Book]]


class Library(ReferrableModel):
    self: Annotated[Href[ForwardRef("Library")], PrimaryKey(type_=uuid.UUID, name="id")]
    books: List[Href[Book]]

    class Config:
        details_view = "get_library"


Library.update_forward_refs()

books: Dict[uuid.UUID, Book] = {}
libraries: Dict[uuid.UUID, Library] = {}

app = FastAPI(middleware=[Middleware(HrefMiddleware)])


@app.get("/libraries/{id}", response_model=Library)
def get_library(id: uuid.UUID):
    library = libraries.get(id)
    if not library:
        raise HTTPException(status_code=404, detail="Library not found")
    return library


@app.post("/libraries")
def post_library(library: LibraryCreate):
    if any(book.key not in books for book in library.books):
        raise HTTPException(
            status_code=400, detail="Trying to add nonexisting book to library"
        )
    new_library = Library(self=uuid.uuid4(), **library.dict())
    libraries[new_library.self.key] = new_library
    return Response(
        status_code=201,
        headers={"Location": new_library.self.url},
    )


@app.get("/books/{id}", response_model=Book)
def get_book(id: uuid.UUID):
    book = books.get(id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@app.post("/books", status_code=204)
def post_book(book: BookCreate):
    new_book = Book(self=uuid.uuid4(), **book.dict())
    books[new_book.self.key] = new_book
    return Response(status_code=201, headers={"Location": new_book.self.url})
