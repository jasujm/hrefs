import pydantic

import pydantic_href
from pydantic_href.href import Href

class User(pydantic.BaseModel):
    pet: Href

def test_parse_id_to_href():
    user = User(pet=1)
    assert user.pet.get_id() == 1
    assert user.pet.get_url() == "/1"

def test_parse_url_to_href():
    user = User(pet="/1")
    assert user.pet.get_id() == 1
    assert user.pet.get_url() == "/1"
