"""Model references"""

import contextlib
import typing

import pydantic
import typing_extensions

KeyType = typing.TypeVar("KeyType")
UrlType = typing.TypeVar("UrlType")


class HrefModel(typing_extensions.Protocol[KeyType, UrlType]):
    """Model that can be used as subject for `Href`"""

    @classmethod
    def href_types(cls) -> typing.Tuple[typing.Type[KeyType], typing.Type[UrlType]]:
        """Return a tuple containing the key and url types, respectively"""
        raise NotImplementedError()

    @classmethod
    def key_to_url(cls, key: KeyType) -> UrlType:
        """Convert key to url"""
        raise NotImplementedError()

    @classmethod
    def url_to_key(cls, url: UrlType) -> KeyType:
        """Convert url to key"""
        raise NotImplementedError()


ModelType = typing.TypeVar("ModelType", bound=HrefModel)


class Href(typing.Generic[ModelType]):
    """Hypertext reference to another model

    Arguments:
      key: the key used by the application to identify the model internally
      url: the URL identifying the model externally (e.g. via REST API)
    """

    def __init__(self, key, url):
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
    def validate(cls, value, field: pydantic.fields.ModelField):
        """Validate reference

        A reference can either be parsed from key or URL.

        Arguments:
          value: key or URL

        Return:
          A ``Href`` object referring to the model identified by the ``value``
          argument
        """
        if not field.sub_fields:
            raise TypeError("Expected sub field")
        model_type: ModelType = field.sub_fields[0].type_
        key_type, url_type = model_type.href_types()
        with contextlib.suppress(pydantic.ValidationError):
            key = pydantic.parse_obj_as(key_type, value)
            return cls(key=key, url=model_type.key_to_url(key))
        with contextlib.suppress(pydantic.ValidationError):
            url = pydantic.parse_obj_as(url_type, value)
            return cls(key=model_type.url_to_key(url), url=url)
        raise TypeError(f"Could not convert {value!r} to either key or url")
