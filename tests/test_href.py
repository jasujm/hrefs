import json

from hypothesis import given, strategies as st
import pydantic
import pytest

from pydantic_href import Href, BaseModel


class Pet(BaseModel):
    id: int

    @staticmethod
    def href_types():
        return int, str

    @staticmethod
    def key_to_url(key: int) -> str:
        return f"/pets/{key}"

    @staticmethod
    def url_to_key(url: str) -> int:
        return int(url.split("/")[-1])


class User(BaseModel):
    pet: Href[Pet]


@given(st.integers())
def test_parse_key_to_href(key):
    user = User(pet=key)
    assert user.pet.get_key() == key
    assert user.pet.get_url() == Pet.key_to_url(key)


@given(st.from_regex(r"\A/pets/\d+\Z"))
def test_parse_url_to_key(url):
    user = User(pet=url)
    assert user.pet.get_key() == Pet.url_to_key(url)
    assert user.pet.get_url() == url


def test_href_definition_with_unparseable_key_fails():
    with pytest.raises(pydantic.ValidationError):
        User(pet=object())


def test_href_definition_without_parameter_fails():
    with pytest.raises(pydantic.ValidationError):
        pydantic.parse_obj_as(Href, 123)


@given(st.integers())
def test_json_encode(key):
    user_json = json.loads(User(pet=key).json())
    assert user_json["pet"] == Pet.key_to_url(key)
