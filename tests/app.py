from typing import List, Dict

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware import Middleware

from hrefs import BaseModel, Href
from hrefs.starlette import ReferrableModel, HrefMiddleware


class Book(ReferrableModel):
    id: int
    title: str

    class Config:
        default_view = "get_book"


class Library(BaseModel):
    id: int
    books: List[Href[Book]]


books: Dict[int, Book] = {}
libraries: Dict[int, Library] = {}

app = FastAPI(middleware=[Middleware(HrefMiddleware)])


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
            status_code=400, detail="Trying to add nonexisting book to library"
        )
    libraries[library.id] = library
    return Response(
        status_code=201,
        headers={"Location": request.url_for("get_library", id=library.id)},
    )


@app.get("/books/{id}", response_model=Book)
def get_book(id: int):
    book = books.get(id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


@app.post("/books", status_code=204)
def post_book(book: Book, request: Request):
    books[book.id] = book
    return Response(
        status_code=201, headers={"Location": request.url_for("get_book", id=book.id)}
    )
