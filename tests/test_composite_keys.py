"""Test for composite primary keys"""

from hypothesis import given, strategies as st, settings, HealthCheck
import pydantic
from typing_extensions import Annotated

from hrefs import Href, BaseReferrableModel, PrimaryKey


class Page(BaseReferrableModel):
    """A model with composite primary key"""

    book_id: Annotated[int, PrimaryKey]
    page_number: Annotated[int, PrimaryKey]


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(page=st.builds(Page))
def test_parse_model_with_composite_key_to_href(page, href_resolver):
    del href_resolver
    href = pydantic.parse_obj_as(Href[Page], page)
    key = (page.book_id, page.page_number)
    assert href.key == key
    assert href.url == Page.key_to_url(key)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(key=st.tuples(st.integers(), st.integers()))
def test_parse_composite_key_to_href(key, href_resolver):
    del href_resolver
    href = pydantic.parse_obj_as(Href[Page], key)
    assert href.key == key
    assert href.url == Page.key_to_url(key)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(url=st.from_regex(r"\Ahttp://example\.com/pages/\d+/\d+\Z"))
def test_parse_composite_url_to_href(url, href_resolver):
    del href_resolver
    href = pydantic.parse_obj_as(Href[Page], url)
    assert href.key == Page.url_to_key(url)
    assert href.url == url
