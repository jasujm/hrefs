from typing import List, Tuple

from hypothesis import given, strategies as st
import pydantic
from typing_extensions import Annotated

from hrefs import Href, BaseReferrableModel, PrimaryKey


class Book(BaseReferrableModel):
    id: int

    @staticmethod
    def key_to_url(key: int) -> str:
        return f"/books/{key}"

    @staticmethod
    def url_to_key(url: str):
        return int(url.split("/")[-1])


class Page(BaseReferrableModel):
    book_id: Annotated[int, PrimaryKey]
    page_number: Annotated[int, PrimaryKey]

    @staticmethod
    def key_to_url(key: Tuple[int, int]) -> str:
        return f"/books/{key[0]}/pages/{key[1]}"

    @staticmethod
    def url_to_key(url: str):
        parts = url.split("/")
        return int(parts[-3]), int(parts[-1])


@given(st.builds(Page))
def test_parse_model_with_composite_key_to_href(page):
    href = pydantic.parse_obj_as(Href[Page], page)
    key = (page.book_id, page.page_number)
    assert href.key == key
    assert href.url == Page.key_to_url(key)


@given(st.tuples(st.integers(), st.integers()))
def test_parse_composite_key_to_href(key):
    href = pydantic.parse_obj_as(Href[Page], key)
    assert href.key == key
    assert href.url == Page.key_to_url(key)


@given(st.from_regex(r"\A/books/\d+/pages/\d+\Z"))
def test_parse_composite_url_to_href(url):
    href = pydantic.parse_obj_as(Href[Page], url)
    assert href.key == Page.url_to_key(url)
    assert href.url == url
