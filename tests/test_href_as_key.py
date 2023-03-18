"""Tests for using hyperlinks as keys"""

# pylint: disable=duplicate-code

from hypothesis import given, strategies as st
import pydantic
import pytest
from typing_extensions import Annotated

from hrefs import Href, BaseReferrableModel, PrimaryKey, ReferrableModelError

pytestmark = pytest.mark.usefixtures("href_resolver")


class Book(BaseReferrableModel):
    """Model that has `self` primary key"""

    self: Annotated[Href["Book"], PrimaryKey(type_=int, name="id")]

    @classmethod
    def _key_to_url_override(cls, key):
        path_params = cls.key_to_params(key)
        return f"http://example.com/books/{path_params['id']}"

    @classmethod
    def _url_to_key_override(cls, url: pydantic.AnyHttpUrl):
        path_params = {"id": int(url.split("/")[-1])}
        key = cls.params_to_key(path_params)
        return key


class BookCover(BaseReferrableModel):
    """Model whose primary key is a hyperlink to another model

    It could model 1-to-1 relationship"""

    book: Annotated[Href[Book], PrimaryKey]

    @classmethod
    def _key_to_url_override(cls, key):
        path_params = cls.key_to_params(key)
        return f"http://example.com/books/{path_params['book_id']}/cover"

    @classmethod
    def _url_to_key_override(cls, url: str):
        parts = url.split("/")
        path_params = {"book_id": int(parts[-2])}
        return cls.params_to_key(path_params)


class Page(BaseReferrableModel):
    """Model that has composite primary key, with one part being a hyperlink

    It could model 1-to-N relationship
    """

    book: Annotated[Href[Book], PrimaryKey]
    page_number: Annotated[int, PrimaryKey]

    @classmethod
    def _key_to_url_override(cls, key):
        path_params = cls.key_to_params(key)
        return f"http://example.com/books/{path_params['book_id']}/pages/{path_params['page_number']}"

    @classmethod
    def _url_to_key_override(cls, url: str):
        parts = url.split("/")
        path_params = {"book_id": int(parts[-3]), "page_number": int(parts[-1])}
        return cls.params_to_key(path_params)


class Bookmark(BaseReferrableModel):
    """Model whose primary key is a hyperlink to a model whose primary key also has hyperlink part

    I'm not sure if this is ever needed in real life, but the library supports it nevertherless
    """

    page: Annotated[Href[Page], PrimaryKey]

    @classmethod
    def _key_to_url_override(cls, key) -> str:
        path_params = cls.key_to_params(key)
        return f"http://example.com/books/{path_params['page_book_id']}/pages/{path_params['page_page_number']}/bookmark"

    @classmethod
    def _url_to_key_override(cls, url: str):
        parts = url.split("/")
        path_params = {
            "page_book_id": int(parts[-4]),
            "page_page_number": int(parts[-2]),
        }
        return cls.params_to_key(path_params)


Book.update_forward_refs()


@given(key=st.integers())
def test_self_href_from_key(key):
    book = Book(self=key)
    assert book.self == Href(key=key, url=Book.key_to_url(key))


@given(url=st.from_regex(r"\Ahttp://example\.com/books/\d+\Z"))
def test_self_href_from_url(url):
    book = Book(self=url)
    assert book.self == Href(key=Book.url_to_key(url), url=url)


@given(book_id=st.from_type(Href[Book]))
def test_parse_href_key_from_referred_model(book_id):
    book = Book(self=book_id)
    href = pydantic.parse_obj_as(Href[BookCover], book)
    assert href.key == book.self
    assert href.url == BookCover.key_to_url(book.self)


@given(book_id=st.integers())
def test_parse_href_key_from_referred_key(book_id):
    href = pydantic.parse_obj_as(Href[BookCover], book_id)
    key = Href(key=book_id, url=Book.key_to_url(book_id))
    assert href.key == key
    assert href.url == BookCover.key_to_url(key)


@given(url=st.from_regex(r"\Ahttp://example\.com/books/\d+/cover\Z"))
def test_parse_href_key_from_referred_url(url):
    href = pydantic.parse_obj_as(Href[BookCover], url)
    assert href.key == BookCover.url_to_key(url)
    assert href.url == url


@given(book_id=st.from_type(Href[Book]), page_number=st.integers())
def test_parse_composite_href_key_from_referred_model(book_id, page_number):
    book = Book(self=book_id)
    href = pydantic.parse_obj_as(Href[Page], (book, page_number))
    assert href.key == (book.self, page_number)
    assert href.url == Page.key_to_url((book.self, page_number))


@given(book_id=st.integers(), page_number=st.integers())
def test_parse_composite_href_key_from_referred_key(book_id, page_number):
    href = pydantic.parse_obj_as(Href[Page], (book_id, page_number))
    key = (Href(key=book_id, url=Book.key_to_url(book_id)), page_number)
    assert href.key == key
    assert href.url == Page.key_to_url(key)


@given(url=st.from_regex(r"\Ahttp://example\.com/books/\d+/pages/\d+\Z"))
def test_parse_composite_href_key_from_referred_url(url):
    href = pydantic.parse_obj_as(Href[Page], url)
    assert href.key == Page.url_to_key(url)
    assert href.url == url


# Only real programmers use model keys that are hrefs to models that also have
# hrefs as model keys


@given(book_id=st.from_type(Href[Book]), page_number=st.integers())
def test_parse_indirect_href_key_from_referred_model(book_id, page_number):
    page = Page(book=book_id, page_number=page_number)
    href = pydantic.parse_obj_as(Href[Bookmark], page)
    assert href.key == pydantic.parse_obj_as(Href[Page], (page.book, page_number))
    assert href.url == Bookmark.key_to_url((page.book, page_number))


@given(book_id=st.integers(), page_number=st.integers())
def test_parse_indirect_href_key_from_referred_key(book_id, page_number):
    href = pydantic.parse_obj_as(Href[Bookmark], (book_id, page_number))
    page_key = (Href(key=book_id, url=Book.key_to_url(book_id)), page_number)
    key = Href(key=page_key, url=Page.key_to_url((book_id, page_number)))
    assert href.key == key
    assert href.url == Bookmark.key_to_url(key)


@given(url=st.from_regex(r"\Ahttp://example\.com/books/\d+/pages/\d+/bookmark\Z"))
def test_parse_indirect_href_key_from_referred_url(url):
    href = pydantic.parse_obj_as(Href[Bookmark], url)
    assert href.key == Bookmark.url_to_key(url)
    assert href.url == url


def test_deep_indirection_is_not_supported() -> None:
    with pytest.raises(ReferrableModelError):

        class _SomeModelWithDeepIndirection(BaseReferrableModel):
            bookmark: Annotated[Href[Bookmark], PrimaryKey]
