"""Tests for the fundamental classes"""

from dataclasses import dataclass
import json
import typing

from packaging import version
from hypothesis import given, strategies as st, assume
import pydantic
import pytest

from hrefs import Href, Referrable


def _pydantic_does_not_support_field_in_modify_schema():
    try:
        return version.parse(pydantic.__version__) < version.Version("1.9")
    except AttributeError:  # pragma: no cover
        return True


@dataclass
class Pet(Referrable[int, str]):
    """A simple referrable type"""

    id: int

    def get_key(self) -> int:
        return self.id

    @staticmethod
    def key_to_url(key: int) -> str:
        return f"/pets/{key}"

    @staticmethod
    def url_to_key(url: str) -> int:
        return int(url.split("/")[-1])


class Owner(pydantic.BaseModel):
    """An owner of many pets"""

    pets: typing.List[Href[Pet]]


@given(st.from_type(Href[Pet]))
def test_parse_href(href):
    assert pydantic.parse_obj_as(Href[Pet], href) is href


@given(st.builds(Pet))
def test_parse_referrable_model(pet):
    href = pydantic.parse_obj_as(Href[Pet], pet)
    assert href.key == pet.id
    assert href.url == Pet.key_to_url(pet.id)


@given(st.integers())
def test_parse_key_to_href(key):
    href = pydantic.parse_obj_as(Href[Pet], key)
    assert href.key == key
    assert href.url == Pet.key_to_url(key)


@given(st.from_regex(r"\A/pets/\d+\Z"))
def test_parse_url_to_key(url):
    href = pydantic.parse_obj_as(Href[Pet], url)
    assert href.key == Pet.url_to_key(url)
    assert href.url == url


def test_parse_href_with_unparseable_key_fails():
    with pytest.raises(pydantic.ValidationError):
        pydantic.parse_obj_as(Href, object())


def test_parse_href_without_parameter_fails():
    with pytest.raises(pydantic.ValidationError):
        pydantic.parse_obj_as(Href, 123)


@given(st.builds(Owner))
def test_json_encode(owner):
    owner_json = json.loads(owner.json())
    assert owner_json["pets"] == [pet.url for pet in owner.pets]


@pytest.mark.skipif(
    _pydantic_does_not_support_field_in_modify_schema(),
    reason="pydantic does not support field argument in __modify_schema__",
)
def test_href_schema() -> None:
    owner_schema = Owner.schema()
    assert owner_schema["properties"]["pets"] == {
        "title": "Pets",
        "type": "array",
        "items": {
            "type": "string",
        },
    }


@given(st.from_type(Href[Pet]))
def test_hash_of_equivalent_hrefs_matches(href):
    other_href = Href(key=href.key, url=href.url)
    assert hash(href) == hash(other_href)


@given(st.from_type(Href[Pet]), st.from_type(Href[Pet]))
def test_hash_of_different_hrefs_differs(href, other_href):
    assume(href != other_href)
    assert hash(href) != hash(other_href)


@given(st.from_type(Href[Pet]))
def test_hypothesis_plugin(href):
    assert isinstance(href, Href)
    assert href.url == Pet.key_to_url(href.key)


@given(st.data())
def test_hypothesis_plugin_plain_href_fails(data):
    with pytest.raises(ValueError):
        data.draw(st.from_type(Href))


@given(st.data())
def test_hypothesis_plugin_href_to_non_referrable_type_fails(data):
    with pytest.raises(ValueError):
        data.draw(st.from_type(Href[int]))
