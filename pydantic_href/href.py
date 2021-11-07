"""Model references"""

import typing

import pydantic


ModelType = typing.TypeVar("ModelType")


class Href(typing.Generic[ModelType]):
    """Hypertext reference to another model

    Arguments:
      key: the key used by the application to identify the model internally
      url: the URL identifying the model externally (e.g. via REST API)
    """

    def __init__(self, key: int, url: str):
        self._key = key
        self._url = url

    def get_key(self):
        """Return the key of the referred object"""
        return self._key

    def get_url(self):
        """Return the URL of the referred object"""
        return self._url

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value: typing.Union[int, str], field: pydantic.fields.ModelField):
        """Validate reference

        A reference can either be parsed from key or URL.

        Arguments:
          value: key or URL

        Return:
          A ``Href`` object referring to the model identified by the ``value``
          argument
        """
        if not field.sub_fields:
            raise TypeError("Expected model type as sub field")
        model_type = field.sub_fields[0].type_
        if isinstance(value, int):
            return cls(key=value, url=model_type.__key_to_url__(value))
        if isinstance(value, str):
            return cls(
                key=model_type.__url_to_key__(value),
                url=value,
            )
        raise TypeError(f"{value} is not int or str")
