import json

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


def test_parse_key_to_href():
    user = User(pet=1)
    assert user.pet.get_key() == 1
    assert user.pet.get_url() == "/pets/1"


def test_parse_url_to_href():
    user = User(pet="/pets/1")
    assert user.pet.get_key() == 1
    assert user.pet.get_url() == "/pets/1"


def test_parse_error():
    with pytest.raises(pydantic.ValidationError):
        User(pet=object())


def test_invalid_href_definition():
    with pytest.raises(pydantic.ValidationError):
        pydantic.parse_obj_as(Href, 123)


def test_json_encode():
    user_json = json.loads(User(pet=1).json())
    assert user_json["pet"] == "/pets/1"
