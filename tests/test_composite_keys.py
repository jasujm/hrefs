"""Test for composite primary keys"""

# pylint: disable=duplicate-code

from hypothesis import given, strategies as st
import pytest
from typing_extensions import Annotated

from hrefs import Href, BaseReferrableModel, PrimaryKey
from hrefs._util import parse_url
from _util import parse_href

pytestmark = pytest.mark.usefixtures("href_resolver")


class Page(BaseReferrableModel):
    """A model with composite primary key"""

    book_id: Annotated[int, PrimaryKey]
    page_number: Annotated[int, PrimaryKey]


@given(page=st.builds(Page))
def test_parse_model_with_composite_key_to_href(page):
    href = parse_href(Page, page)
    key = (page.book_id, page.page_number)
    assert href.key == key
    assert href.url == Page.key_to_url(key)


@given(key=st.tuples(st.integers(), st.integers()))
def test_parse_composite_key_to_href(key):
    href = parse_href(Page, key)
    assert href.key == key
    assert href.url == Page.key_to_url(key)


@given(url=st.from_regex(r"\Ahttp://example\.com/pages/[0-9]+/[0-9]+\Z"))
def test_parse_composite_url_to_href(url):
    href = parse_href(Page, url)
    assert href.key == Page.url_to_key(url)
    assert href.url == parse_url(url)
