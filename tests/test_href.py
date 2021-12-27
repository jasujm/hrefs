import json
import typing

from hypothesis import given, strategies as st
import pydantic
import pytest
from typing_extensions import Annotated

from hrefs import Href, BaseReferrableModel, PrimaryKey
from util import hrefs


class Pet(BaseReferrableModel):
    id: int

    @staticmethod
    def key_to_url(key: int) -> str:
        return f"/pets/{key}"

    @staticmethod
    def url_to_key(url: str):
        return int(url.split("/")[-1])


class Owner(pydantic.BaseModel):
    pets: typing.List[Href[Pet]]


pet_hrefs = hrefs(Pet, st.integers())


@given(pet_hrefs)
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


@given(st.builds(Owner, pets=st.lists(pet_hrefs)))
def test_json_encode(owner):
    owner_json = json.loads(owner.json())
    assert owner_json["pets"] == [pet.url for pet in owner.pets]


@given(st.integers())
def test_primary_key_annotation(my_id):
    class MyModel(BaseReferrableModel):
        my_id: Annotated[int, PrimaryKey]

        @staticmethod
        def key_to_url(key: int) -> None:
            ...

        @staticmethod
        def url_to_key(url: str):
            ...

    assert MyModel(my_id=my_id).get_key() == my_id


def test_multiple_primary_key_annotations_fails():
    with pytest.raises(TypeError):

        class MyModel(BaseReferrableModel):
            my_id: Annotated[int, PrimaryKey, PrimaryKey]

            @staticmethod
            def key_to_url(key: int) -> None:
                ...

            @staticmethod
            def url_to_key(url: str):
                ...


def test_href_forward_reference():
    class MyModel(BaseReferrableModel):
        id: int
        self: Href["MyModel"]

        @pydantic.root_validator(pre=True)
        def populate_self(cls, values):
            values["self"] = values["id"]
            return values

        @staticmethod
        def key_to_url(key: int) -> None:
            return f"/{key}"

        @staticmethod
        def url_to_key(url: str):
            ...

    MyModel.update_forward_refs()

    assert MyModel(id=1).self == Href(key=1, url="/1")


@given(st.integers(), st.floats())
def test_derived_model_inherits_referrable_properties(key, purr_frequency):
    class Cat(Pet):
        purr_frequency: float
    cat = Cat(id=key, my_id=key, purr_frequency=purr_frequency)
    href = pydantic.parse_obj_as(Href[Cat], cat)
    assert href.key == key
    assert href.url == Pet.key_to_url(key)
