"""Test for referrable pydantic models"""

from hypothesis import given, strategies as st
import pydantic
import pytest
from typing_extensions import Annotated

from hrefs import BaseReferrableModel, PrimaryKey, Href

pytestmark = pytest.mark.usefixtures("href_resolver")


def test_base_referrable_model_has_empty_key():
    href = pydantic.parse_obj_as(Href[BaseReferrableModel], BaseReferrableModel())
    assert href.key == ()
    assert href.url == BaseReferrableModel.key_to_url(())


@given(st.integers())
def test_simple_model(id) -> None:
    class _SimpleModel(BaseReferrableModel):
        id: int

    assert _SimpleModel(id=id).get_key() == id


@given(st.integers())
def test_primary_key_annotation(my_id) -> None:
    class _MyModel(BaseReferrableModel):
        my_id: Annotated[int, PrimaryKey]

    assert _MyModel(my_id=my_id).get_key() == my_id


def test_multiple_primary_key_annotations_fails() -> None:
    with pytest.raises(TypeError):

        class _MyModel(BaseReferrableModel):
            my_id: Annotated[int, PrimaryKey, PrimaryKey]


def test_href_forward_reference() -> None:
    class _MyModel(BaseReferrableModel):
        id: int
        self: Href["_MyModel"]

        @pydantic.root_validator(pre=True)
        def _populate_self(cls, values):  # pylint: disable=no-self-argument
            values["self"] = values["id"]
            return values

    _MyModel.update_forward_refs()

    assert _MyModel(id=1).self == Href(key=1, url="http://example.com/_mymodels/1")


@given(key=st.integers(), purr_frequency=st.floats())
def test_derived_model_inherits_referrable_properties(key, purr_frequency) -> None:
    class _Pet(BaseReferrableModel):
        id: int

    class _Cat(_Pet):
        purr_frequency: float

    cat = _Cat(id=key, purr_frequency=purr_frequency)
    href = pydantic.parse_obj_as(Href[_Cat], cat)
    assert href.key == key
    assert href.url == _Cat.key_to_url(key)
