import json
import typing

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
    pets: typing.List[Href[Pet]]


hrefs = st.integers().map(
    lambda key: Href(key=key, url=Pet.key_to_url(key), target=Pet)
)


@given(hrefs)
def test_parse_href(href):
    assert pydantic.parse_obj_as(Href[Pet], href) is href


@given(st.builds(Pet))
def test_parse_referrable_model(pet):
    href = pydantic.parse_obj_as(Href[Pet], pet)
    assert href.get_key() == pet.id
    assert href.get_url() == Pet.key_to_url(pet.id)


@given(st.integers())
def test_parse_key_to_href(key):
    href = pydantic.parse_obj_as(Href[Pet], key)
    assert href.get_key() == key
    assert href.get_url() == Pet.key_to_url(key)


@given(st.from_regex(r"\A/pets/\d+\Z"))
def test_parse_url_to_key(url):
    href = pydantic.parse_obj_as(Href[Pet], url)
    assert href.get_key() == Pet.url_to_key(url)
    assert href.get_url() == url


def test_parse_href_with_unparseable_key_fails():
    with pytest.raises(pydantic.ValidationError):
        pydantic.parse_obj_as(Href, object())


def test_parse_href_without_parameter_fails():
    with pytest.raises(pydantic.ValidationError):
        pydantic.parse_obj_as(Href, 123)


@given(st.builds(Owner, pets=st.lists(hrefs)))
def test_json_encode(owner):
    owner_json = json.loads(owner.json())
    assert owner_json["pets"] == [pet.get_url() for pet in owner.pets]
