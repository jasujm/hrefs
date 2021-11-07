import pydantic
import pytest

from pydantic_href import Href


class Pet(pydantic.BaseModel):
    id: int

    @staticmethod
    def __key_to_url__(key: int):
        return f"/pets/{key}"

    @staticmethod
    def __url_to_key__(url: str):
        return int(url.split("/")[-1])


class User(pydantic.BaseModel):
    pet: Href[Pet]


def test_parse_id_to_href():
    user = User(pet=1)
    assert user.pet.get_key() == 1
    assert user.pet.get_url() == "/pets/1"


def test_parse_url_to_href():
    user = User(pet="/pets/1")
    assert user.pet.get_key() == 1
    assert user.pet.get_url() == "/pets/1"


def test_parse_error():
    with pytest.raises(pydantic.ValidationError):
        User(pet=3.14)


def test_invalid_href_definition():
    with pytest.raises(pydantic.ValidationError):
        pydantic.parse_obj_as(Href, 123)
