"""Test for referrable pydantic models"""

from hypothesis import given, strategies as st
import pydantic
import pytest
from typing_extensions import Annotated

from hrefs import BaseReferrableModel, PrimaryKey, Href, ReferrableModelError

pytestmark = pytest.mark.usefixtures("href_resolver")


def test_base_referrable_model_has_empty_key():
    href = pydantic.parse_obj_as(Href[BaseReferrableModel], BaseReferrableModel())
    assert href.key == ()
    assert href.url == BaseReferrableModel.key_to_url(())


@given(st.integers())
def test_simple_model(id) -> None:
    class _SimpleModel(BaseReferrableModel):
        id: int

    model = _SimpleModel(id=id)
    href = pydantic.parse_obj_as(Href[_SimpleModel], model)
    assert href.key == id
    assert href.url == _SimpleModel.key_to_url(id)
    assert href == pydantic.parse_obj_as(Href[_SimpleModel], href.url)


@given(st.integers())
def test_primary_key_annotation(my_id) -> None:
    class _MyModel(BaseReferrableModel):
        my_id: Annotated[int, PrimaryKey]

    model = _MyModel(my_id=my_id)
    href = pydantic.parse_obj_as(Href[_MyModel], model)
    assert href.key == my_id
    assert href.url == _MyModel.key_to_url(my_id)
    assert href == pydantic.parse_obj_as(Href[_MyModel], href.url)


def test_multiple_primary_key_annotations_fails() -> None:
    with pytest.raises(ReferrableModelError):

        class _MyModel(BaseReferrableModel):
            my_id: Annotated[int, PrimaryKey, PrimaryKey]


@given(st.integers())
def test_href_forward_reference(id) -> None:
    class _MyModel(BaseReferrableModel):
        id: int
        self: Href["_MyModel"]

        @pydantic.root_validator(pre=True, allow_reuse=True)
        def _populate_self(cls, values):  # pylint: disable=no-self-argument
            values["self"] = values["id"]
            return values

    _MyModel.update_forward_refs()

    model = _MyModel(id=id)
    href = pydantic.parse_obj_as(Href[_MyModel], model)
    assert model.self == href
    assert href.key == id
    assert href.url == _MyModel.key_to_url(id)
    assert href == pydantic.parse_obj_as(Href[_MyModel], href.url)


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
    assert href == pydantic.parse_obj_as(Href[_Cat], href.url)
