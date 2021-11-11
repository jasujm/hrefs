"""Base models for referring and referrable types"""

import abc
import inspect
import typing

import pydantic

from .href import Href


def _extract_type(meth: typing.Callable) -> typing.Type:
    return_annotation = inspect.signature(meth).return_annotation
    assert (
        return_annotation != inspect.Signature.empty
    ), f"return annotation of {meth!r} unexpectedly empty"
    return return_annotation


class BaseModel(pydantic.BaseModel):
    """Pydantic model using href features"""

    class Config:
        """Common model configuration"""

        json_encoders = {Href: lambda h: h.get_url()}


class ReferrableModel(BaseModel, abc.ABC):
    """Stub implementation of the `href.ReferrableModel` protocol

    The abstract base implements `href_types()` which works by inferring the
    return type from annotations.

    The abstract base implements `get_key()` which works by returning the `id`
    property that the class is expected to have. Having `id` property is
    optional, and a subclass may override `get_key()` instead.

    The subclass needs to implement `key_to_url()` and `url_to_key()`, and
    annotate their return type accordingly.
    """

    def get_key(self):
        """Return the `id` property of the model"""
        return getattr(self, "id")

    @classmethod
    def href_types(cls):
        """Return a tuple containing the key and url types, respectively"""
        return _extract_type(cls.url_to_key), _extract_type(cls.key_to_url)

    @classmethod
    @abc.abstractmethod
    def key_to_url(cls, key):
        """Convert key to url"""
        raise NotImplementedError()

    @classmethod
    @abc.abstractmethod
    def url_to_key(cls, url):
        """Convert url to key"""
        raise NotImplementedError()
