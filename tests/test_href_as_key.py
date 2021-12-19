from typing import ForwardRef

from hypothesis import given, strategies as st
import pydantic
from typing_extensions import Annotated

from hrefs import Href, BaseReferrableModel, PrimaryKey
from util import hrefs


class Book(BaseReferrableModel):
    self: Annotated[Href[ForwardRef("Book")], PrimaryKey(type_=int)]

    @staticmethod
    def key_to_url(key: int) -> str:
        return f"/books/{key}"

    @staticmethod
    def url_to_key(url: str) -> int:
        return int(url.split("/")[-1])


class BookCover(BaseReferrableModel):
    book: Annotated[Href[Book], PrimaryKey]

    @staticmethod
    def key_to_url(book: Href[Book]) -> str:
        return f"/books/{book.key}/cover"

    @staticmethod
    def url_to_key(url: str) -> Href[Book]:
        parts = url.split("/")
        return Href(key=int(parts[-2]), url="/".join(parts[:-1]))


Book.update_forward_refs()

book_hrefs = hrefs(Book, st.integers())


@given(st.integers())
def test_self_href_from_key(key):
    book = Book(self=key)
    assert book.self == Href(key=key, url=Book.key_to_url(key))


@given(st.from_regex(r"\A/books/\d+\Z"))
def test_self_href_from_url(url):
    book = Book(self=url)
    assert book.self == Href(key=Book.url_to_key(url), url=url)


@given(book_hrefs)
def test_parse_href_key_from_referred_model(book_self):
    book = Book(self=book_self)
    href = pydantic.parse_obj_as(Href[BookCover], book)
    assert href.key == book.self
    assert href.url == BookCover.key_to_url(book.self)


@given(st.integers())
def test_parse_href_key_from_referred_key(book_id):
    href = pydantic.parse_obj_as(Href[BookCover], book_id)
    key = Href(key=book_id, url=Book.key_to_url(book_id))
    assert href.key == key
    assert href.url == BookCover.key_to_url(key)


@given(st.from_regex(r"\A/books/\d+/cover\Z"))
def test_parse_href_key_from_referred_url(url):
    href = pydantic.parse_obj_as(Href[BookCover], url)
    assert href.key == BookCover.url_to_key(url)
    assert href.url == url
