import json

from hypothesis import given, strategies as st
import pydantic
import pytest

from pydantic_href import Href, BaseModel, ReferrableModel


class Pet(ReferrableModel):
    id: int

    @staticmethod
    def key_to_url(key: int) -> str:
        return f"/pets/{key}"

    @staticmethod
    def url_to_key(url: str) -> int:
        return int(url.split("/")[-1])


class Owner(BaseModel):
    pet: Href[Pet]


hrefs = st.integers().map(
    lambda key: Href(key=key, url=Pet.key_to_url(key), target=Pet)
)


@given(hrefs)
def test_parse_href(href):
    assert Owner(pet=href).pet is href


@given(st.builds(Pet))
def test_parse_referrable_model(pet):
    owner = Owner(pet=pet)
    assert owner.pet.get_key() == pet.id
    assert owner.pet.get_url() == Pet.key_to_url(pet.id)


@given(st.integers())
def test_parse_key_to_href(key):
    owner = Owner(pet=key)
    assert owner.pet.get_key() == key
    assert owner.pet.get_url() == Pet.key_to_url(key)


@given(st.from_regex(r"\A/pets/\d+\Z"))
def test_parse_url_to_key(url):
    owner = Owner(pet=url)
    assert owner.pet.get_key() == Pet.url_to_key(url)
    assert owner.pet.get_url() == url


def test_parse_href_with_unparseable_key_fails():
    with pytest.raises(pydantic.ValidationError):
        Owner(pet=object())


def test_parse_href_without_parameter_fails():
    with pytest.raises(pydantic.ValidationError):
        pydantic.parse_obj_as(Href, 123)


@given(st.integers())
def test_json_encode(key):
    owner_json = json.loads(Owner(pet=key).json())
    assert owner_json["pet"] == Pet.key_to_url(key)
