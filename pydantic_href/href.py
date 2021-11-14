"""Model references"""

import abc
import contextlib
import inspect
import typing

import pydantic
import typing_extensions

KeyType = typing.TypeVar("KeyType")
UrlType = typing.TypeVar("UrlType")


def _extract_type(meth: typing.Callable) -> typing.Type:
    return_annotation = inspect.signature(meth).return_annotation
    assert (
        return_annotation != inspect.Signature.empty
    ), f"return annotation of {meth!r} unexpectedly empty"
    return return_annotation


class Referrable(typing_extensions.Protocol[KeyType, UrlType]):
    """Protocol that needs to be implemented by a subject of `Href`

    `Referrable` also acts as an ABC. The subclass needs to implement at least
    `key_to_url()` and `url_to_key()` to be able to convert between key and url
    representstions. The return type of these function need to be annotated
    appropriately to exploit the default implementation of `href_types()`.

    The abstract base implements `href_types()` which works by inferring the
    return type from annotations.

    The abstract base implements `get_key()` which works by returning the `id`
    property that the class is expected to have. Having `id` property is
    optional, and a subclass may override `get_key()` instead.

    """

    def get_key(self) -> KeyType:
        """Return the key of the model"""
        return getattr(self, "id")

    @classmethod
    def href_types(cls) -> typing.Tuple[typing.Type[KeyType], typing.Type[UrlType]]:
        """Return a tuple containing the key and url types, respectively"""
        return _extract_type(cls.url_to_key), _extract_type(cls.key_to_url)

    @classmethod
    @abc.abstractmethod
    def key_to_url(cls, key: KeyType) -> UrlType:
        """Convert key to url"""
        raise NotImplementedError()

    @classmethod
    @abc.abstractmethod
    def url_to_key(cls, url: UrlType) -> KeyType:
        """Convert url to key"""
        raise NotImplementedError()


ReferrableType = typing.TypeVar("ReferrableType", bound=Referrable)


class Href(typing.Generic[ReferrableType]):
    """Hypertext reference to another model

    Arguments:
      key: the key used by the application to identify the model internally
      url: the URL identifying the model externally (e.g. via REST API)
      target: The target type
    """

    __slots__ = ["_key", "_url", "_target"]

    def __init__(self, key, url, target: typing.Type[ReferrableType]):
        self._key = key
        self._url = url
        self._target = target

    def __repr__(self):
        return f"Href(key={self._key!r}, url={self._url!r}, target={self._target.__name__})"

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

        Arguments:
          value: Parsed object. Can be either key, url, an instance of the target type
                 or a `Href` object with compatible target type.

        Return:
          A `Href` object referring to the model identified by the `value`
          argument
        """
        if not field.sub_fields:
            raise TypeError("Expected sub field")
        model_type: typing.Type[ReferrableType] = field.sub_fields[0].type_
        # pylint:disable=protected-access
        if isinstance(value, cls):
            return value
        if isinstance(value, model_type):
            key = value.get_key()
            return cls._from_key(key, model_type)
        key_type, url_type = model_type.href_types()
        with contextlib.suppress(pydantic.ValidationError):
            key = pydantic.parse_obj_as(key_type, value)
            return cls._from_key(key, model_type)
        with contextlib.suppress(pydantic.ValidationError):
            url = pydantic.parse_obj_as(url_type, value)
            return cls._from_url(url, model_type)
        raise TypeError(f"Could not convert {value!r} to either key or url")

    @classmethod
    def _from_key(cls, key: KeyType, model_type: typing.Type[ReferrableType]):
        return cls(key=key, url=model_type.key_to_url(key), target=model_type)

    @classmethod
    def _from_url(cls, url: UrlType, model_type: typing.Type[ReferrableType]):
        return cls(key=model_type.url_to_key(url), url=url, target=model_type)
