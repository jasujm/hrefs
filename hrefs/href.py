"""Model references"""

import abc
import contextlib
import inspect
import operator
import typing
import warnings

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
    """Protocol that needs to be implemented by a target of :class:`Href`

    The class can either be used as a protocol (see `PEP 544
    <https://www.python.org/dev/peps/pep-0544/>`_).

    * When used as protocol in type annotations, :class:`Referrable` is
      parametrized by key and URL types, respectively. For example
      ``Referrable[int, str]`` annotates a referrable type having ``int`` as key
      and ``str`` as URL. ``Referrable[UUID, AnyHttpUrl]`` annotates a
      referrable type having ``UUID`` key and ``AnyHttpUrl`` as URL type.

    * When used as abstract base class, the subclass needs to implement at least
      :func:`key_to_url()` and :func:`url_to_key()` to specify the conversions
      between the key and URL representations. The return types of the functions
      should be annotated to make them available for parsing and serialization
      at runtime. Moreover, the default implementation assumes that the has
      ``id`` property used as the key of the referrable. Here is an example:

      .. code-block:: python

         class Book(Referrable):
             id: int

             @classmethod
             def key_to_url(key: int) -> str:
                 return f"/books/{key}"

             @classmethod
             def url_to_key(url: str) -> int:
                 return url.split("/")[-1]

    """

    def get_key(self) -> KeyType:
        """Return the key of the model

        The default implementation returns the ``id`` property of the object.
        """
        return getattr(self, "id")

    @classmethod
    def href_types(cls) -> typing.Tuple[typing.Type[KeyType], typing.Type[UrlType]]:
        """Return a tuple containing the key and url types, respectively

        The default implementation returns the return type annotations of
        :func:`url_to_key()` and :func:`key_to_url()`, respectively.
        """
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

    The class is generic and can be annotated by a type implementing the
    :class:`Referrable` protocol. If ``Book`` is assumed to be a type
    implementing :class:`Referrable`, then ``Href[Book]`` represents a hyperlink
    to a book. This mechanism primarily exists for the benefit of pydantic, and
    allows the validation to know what kind of reference it is working with (see
    :ref:`quickstart`).

    """

    __slots__ = ["_key", "_url"]

    def __init__(self, key, url):
        """
        Arguments:
          key: the key used by the application to identify the model internally
          url: the URL identifying the model externally (e.g. via REST API)
        """
        self._key = key
        self._url = url

    def __repr__(self):
        return f"Href(key={self._key!r}, url={self._url!r})"

    @property
    def key(self):
        """The key of the referred object"""
        return self._key

    @property
    def url(self):
        """The URL of the referred object"""
        return self._url

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value, field: pydantic.fields.ModelField):
        """Parse ``value`` into hyperlink

        This method mainly exists for integration to pydantic. A user rarely
        needs to call it directly.

        Arguments:
          value:

            The parsed object. It can be either:

            * Another :class:`Href` instance
            * An instance of the referred model
            * A value of the key type (interpreted as key identifying the referred object)
            * A url string (interpreted as URL to the referred object)

        Returns:
          A :class:`Href` object referring the model identified by the ``value``
          argument.

        Raises:
          TypeError: If the :class:`Href` model isn't properly annotated, or if
            ``value`` doesn't conform to any of the recognized types
          Exception: In addition passes any exceptions happening during conversions

        """
        if not field.sub_fields:
            raise TypeError("Expected sub field")
        model_type: typing.Type[ReferrableType] = field.sub_fields[0].type_
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

    @staticmethod
    def __modify_schema__(schema: typing.MutableMapping[str, typing.Any]):
        # By default pydantic will use the schema of `ReferrableModel`. That is
        # wrong for `Href`, but without runtime type of `ReferrableModel` or
        # being extremely hacky, I can't do much beyond clearing the schema spec
        # (that translates to "any" type in OpenAPI).
        # See: https://github.com/jasujm/hrefs/issues/3
        schema.clear()
        schema["title"] = "Href"

    @classmethod
    def _from_key(cls, key: KeyType, model_type: typing.Type[ReferrableType]):
        return cls(key=key, url=model_type.key_to_url(key))

    @classmethod
    def _from_url(cls, url: UrlType, model_type: typing.Type[ReferrableType]):
        return cls(key=model_type.url_to_key(url), url=url)


try:
    from pydantic.json import ENCODERS_BY_TYPE
except ImportError:
    warnings.warn(
        "Failed to add Href encoder. This may affect serializing Href instances to json.",
        ImportWarning,
    )
else:
    ENCODERS_BY_TYPE[Href] = operator.attrgetter("url")
