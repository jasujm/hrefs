from typing import ForwardRef

from hypothesis import given, strategies as st
import pydantic
import pytest
from typing_extensions import Annotated

from hrefs import Href, BaseReferrableModel, PrimaryKey
from util import hrefs


class Book(BaseReferrableModel):
    self: Annotated[Href[ForwardRef("Book")], PrimaryKey(type_=int)]

    @classmethod
    def key_to_url(cls, key) -> str:
        path_params = cls.key_to_path_params(key)
        return f"/books/{path_params['self']}"

    @classmethod
    def url_to_key(cls, url: str) -> int:
        path_params = {"self": int(url.split("/")[-1])}
        key = cls.path_params_to_key(path_params)
        return path_params["self"]


class BookCover(BaseReferrableModel):
    book: Annotated[Href[Book], PrimaryKey]

    @classmethod
    def key_to_url(cls, key) -> str:
        path_params = cls.key_to_path_params(key)
        return f"/books/{path_params['book_self']}/cover"

    @classmethod
    def url_to_key(cls, url: str):
        parts = url.split("/")
        path_params = {"book_self": int(parts[-2])}
        return cls.path_params_to_key(path_params)


class Page(BaseReferrableModel):
    book: Annotated[Href[Book], PrimaryKey]
    page_number: Annotated[int, PrimaryKey]

    @classmethod
    def key_to_url(cls, key) -> str:
        path_params = cls.key_to_path_params(key)
        return f"/books/{path_params['book_self']}/pages/{path_params['page_number']}"

    @classmethod
    def url_to_key(cls, url: str):
        parts = url.split("/")
        path_params = {"book_self": int(parts[-3]), "page_number": int(parts[-1])}
        return cls.path_params_to_key(path_params)


class Bookmark(BaseReferrableModel):
    page: Annotated[Href[Page], PrimaryKey]

    @classmethod
    def key_to_url(cls, key) -> str:
        path_params = cls.key_to_path_params(key)
        return f"/books/{path_params['page_book_self']}/pages/{path_params['page_page_number']}/bookmark"

    @classmethod
    def url_to_key(cls, url: str):
        parts = url.split("/")
        path_params = {
            "page_book_self": int(parts[-4]),
            "page_page_number": int(parts[-2]),
        }
        return cls.path_params_to_key(path_params)


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


@given(book_hrefs, st.integers())
def test_parse_composite_href_key_from_referred_model(book_self, page_number):
    book = Book(self=book_self)
    href = pydantic.parse_obj_as(Href[Page], (book, page_number))
    assert href.key == (book.self, page_number)
    assert href.url == Page.key_to_url((book.self, page_number))


@given(st.integers(), st.integers())
def test_parse_composite_href_key_from_referred_key(book_id, page_number):
    href = pydantic.parse_obj_as(Href[Page], (book_id, page_number))
    key = (Href(key=book_id, url=Book.key_to_url(book_id)), page_number)
    assert href.key == key
    assert href.url == Page.key_to_url(key)


@given(st.from_regex(r"\A/books/\d+/pages/\d+\Z"))
def test_parse_composite_href_key_from_referred_url(url):
    href = pydantic.parse_obj_as(Href[Page], url)
    assert href.key == Page.url_to_key(url)
    assert href.url == url


# Only real programmers use model keys that are hrefs to models that also have
# hrefs as model keys


@given(book_hrefs, st.integers())
def test_parse_indirect_href_key_from_referred_model(book_self, page_number):
    page = Page(book=book_self, page_number=page_number)
    href = pydantic.parse_obj_as(Href[Bookmark], page)
    assert href.key == pydantic.parse_obj_as(Href[Page], (page.book, page_number))
    assert href.url == Bookmark.key_to_url((page.book, page_number))


@given(st.integers(), st.integers())
def test_parse_indirect_href_key_from_referred_key(book_id, page_number):
    href = pydantic.parse_obj_as(Href[Bookmark], (book_id, page_number))
    page_key = (Href(key=book_id, url=Book.key_to_url(book_id)), page_number)
    key = Href(key=page_key, url=Page.key_to_url((book_id, page_number)))
    assert href.key == key
    assert href.url == Bookmark.key_to_url(key)


@given(st.from_regex(r"\A/books/\d+/pages/\d+/bookmark\Z"))
def test_parse_indirect_href_key_from_referred_url(url):
    href = pydantic.parse_obj_as(Href[Bookmark], url)
    assert href.key == Bookmark.url_to_key(url)
    assert href.url == url


def test_deep_indirection_is_not_supported():
    with pytest.raises(TypeError, match="not supported"):

        class SomeModelWithDeepIndirection(BaseReferrableModel):
            bookmark: Annotated[Href[Bookmark], PrimaryKey]
