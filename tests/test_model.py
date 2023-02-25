"""Test for referrable pydantic models"""

from hypothesis import given, strategies as st, settings, HealthCheck
import pytest

import pydantic
from typing_extensions import Annotated

from hrefs import BaseReferrableModel, PrimaryKey, Href


@given(st.integers())
def test_primary_key_annotation(my_id) -> None:
    class _MyModel(BaseReferrableModel):
        my_id: Annotated[int, PrimaryKey]

    assert _MyModel(my_id=my_id).get_key() == my_id


def test_multiple_primary_key_annotations_fails() -> None:
    with pytest.raises(TypeError):

        class _MyModel(BaseReferrableModel):
            my_id: Annotated[int, PrimaryKey, PrimaryKey]


def test_href_forward_reference(href_resolver) -> None:
    del href_resolver

    class _MyModel(BaseReferrableModel):
        id: int
        self: Href["_MyModel"]

        @pydantic.root_validator(pre=True)
        def _populate_self(cls, values):  # pylint: disable=no-self-argument
            values["self"] = values["id"]
            return values

    _MyModel.update_forward_refs()

    assert _MyModel(id=1).self == Href(key=1, url="http://example.com/_mymodels/1")


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(key=st.integers(), purr_frequency=st.floats())
def test_derived_model_inherits_referrable_properties(
    key, purr_frequency, href_resolver
) -> None:
    del href_resolver

    class _Pet(BaseReferrableModel):
        id: int

    class _Cat(_Pet):
        purr_frequency: float

    cat = _Cat(id=key, purr_frequency=purr_frequency)
    href = pydantic.parse_obj_as(Href[_Cat], cat)
    assert href.key == key
    assert href.url == _Cat.key_to_url(key)
