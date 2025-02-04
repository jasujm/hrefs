"""Test for referrable pydantic models"""

from typing import Annotated

from hypothesis import given, strategies as st
import pydantic
import pytest

from _util import parse_href
from hrefs import BaseReferrableModel, PrimaryKey, Href, ReferrableModelError
from hrefs._util import is_pydantic_2

pytestmark = pytest.mark.usefixtures("href_resolver")


class ModelWithForwardReference(pydantic.BaseModel):
    """Model that uses hyperlink via forward reference"""

    link: Href["ModelReferredViaForwardReference"]


class ModelReferredViaForwardReference(BaseReferrableModel):
    """Target of hyperlink via forward reference"""

    id: int


if not is_pydantic_2():
    ModelWithForwardReference.update_forward_refs()


def test_base_referrable_model_has_empty_key():
    href = parse_href(BaseReferrableModel, BaseReferrableModel())
    assert href.key == ()
    assert href.url == BaseReferrableModel.key_to_url(())


@given(st.integers())
def test_simple_model(id) -> None:
    class _SimpleModel(BaseReferrableModel):
        id: int

    model = _SimpleModel(id=id)
    href = parse_href(_SimpleModel, model)
    assert href.key == id
    assert href.url == _SimpleModel.key_to_url(id)
    assert href == parse_href(_SimpleModel, href.url)


@given(st.integers())
def test_primary_key_annotation(my_id) -> None:
    class _MyModel(BaseReferrableModel):
        my_id: Annotated[int, PrimaryKey]

    model = _MyModel(my_id=my_id)
    href = parse_href(_MyModel, model)
    assert href.key == my_id
    assert href.url == _MyModel.key_to_url(my_id)
    assert href == parse_href(_MyModel, href.url)


def test_multiple_primary_key_annotations_fails() -> None:
    with pytest.raises(ReferrableModelError):

        class _MyModel(BaseReferrableModel):
            my_id: Annotated[int, PrimaryKey, PrimaryKey]


@given(st.integers())
def test_href_to_self(id) -> None:
    validator_decorator = (
        pydantic.model_validator(mode="before")
        if is_pydantic_2()
        else pydantic.root_validator(pre=True, allow_reuse=True)
    )

    class _MyModel(BaseReferrableModel):
        id: int
        self: Href["_MyModel"]

        @validator_decorator  # type: ignore
        def _populate_self(cls, values):  # pylint: disable=no-self-argument
            values["self"] = values["id"]
            return values

    if not is_pydantic_2():
        _MyModel.update_forward_refs()

    model = _MyModel(id=id)
    href = parse_href(_MyModel, model)
    assert model.self == href
    assert href.key == id
    assert href.url == _MyModel.key_to_url(id)
    assert href == parse_href(_MyModel, href.url)


@given(st.integers())
def test_href_forward_reference(id) -> None:
    assert ModelWithForwardReference(link=id).link == parse_href(
        ModelReferredViaForwardReference, id
    )


@given(key=st.integers(), purr_frequency=st.floats())
def test_derived_model_inherits_referrable_properties(key, purr_frequency) -> None:
    class _Pet(BaseReferrableModel):
        id: int

    class _Cat(_Pet):
        purr_frequency: float

    cat = _Cat(id=key, purr_frequency=purr_frequency)
    href = parse_href(_Cat, cat)
    assert href.key == key
    assert href.url == _Cat.key_to_url(key)
    assert href == parse_href(_Cat, href.url)


def test_simple_model_has_simple_key() -> None:
    class _SimpleModel(BaseReferrableModel):
        id: int

    assert _SimpleModel.has_simple_key()
