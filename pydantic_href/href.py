"""Model references"""

import pydantic

class Href:
    """Href to another model"""

    def __init__(self, id: int, url: pydantic.AnyHttpUrl):
        self._id = id
        self._url = url

    def get_id(self):
        return self._id

    def get_url(self):
        return self._url

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, int):
            return cls(id=v, url=f"/{v}")
        if isinstance(v, str):
            return cls(id=int(v.split("/")[-1]), url=v)
        raise TypeError(f"{v} is not int or str")
