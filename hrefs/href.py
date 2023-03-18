"""The core hyperlink types"""

import abc
import inspect
import operator
import typing
import warnings

import pydantic

T = typing.TypeVar("T")
KeyType = typing.TypeVar("KeyType")  # pylint: disable=invalid-name
UrlType = typing.TypeVar("UrlType")  # pylint: disable=invalid-name


if typing.TYPE_CHECKING:  # pragma: no cover
    import pydantic.fields


def _get_return_annotation(meth: typing.Callable) -> typing.Type:
    return_annotation = inspect.signature(meth).return_annotation
    assert (
        return_annotation != inspect.Signature.empty
    ), f"return annotation of {meth!r} unexpectedly empty"
    return return_annotation


def _try_convert(
    meth: typing.Callable[..., T], value: typing.Any
) -> typing.Optional[T]:
    return_annotation = _get_return_annotation(meth)
    try:
        return return_annotation(value)
    except (TypeError, ValueError):
        return None


class Referrable(typing.Generic[KeyType, UrlType], metaclass=abc.ABCMeta):
    """Abstract base class for the targets of :class:`Href`

    The subclass needs to implement at least :meth:`get_key()` to convert
    between model and key, and :meth:`key_to_url()` and :meth:`url_to_key()` to
    specify the conversions between the key and URL representations.  The return
    types of the functions should be annotated to make them available for
    parsing and serialization at runtime.  Here is an example:

    .. code-block:: python

        class Book(Referrable[int, str]):
            id: int

            def get_key(self) -> int:
                return self.id

            @staticmethod
            def key_to_url(key: int) -> str:
                return f"/books/{key}"

            @staticmethod
            def url_to_key(url: str) -> int:
                return url.split("/")[-1]
    """

    @abc.abstractmethod
    def get_key(self) -> KeyType:
        """Return the key of the model"""
        raise NotImplementedError()  # pragma: no cover

    @classmethod
    def parse_as_key(cls, value: typing.Any) -> typing.Optional[KeyType]:
        """Attempt to parse ``value`` as key

        The default implementation reads the return type annotation of
        :meth:`url_to_key()`, and tries to convert ``value``, swallowing
        ``TypeError`` and ``ValueError``.

        Return:
            ``value`` parameter converted to key type, or ``None`` if unable to
            parse
        """
        return _try_convert(cls.url_to_key, value)

    @classmethod
    def parse_as_url(cls, value: typing.Any) -> typing.Optional[UrlType]:
        """Attempt to parse ``value`` as URL

        The default implementation reads the return type annotation of
        :meth:`key_to_url()`, and tries to convert ``value``, swallowing
        ``TypeError`` and ``ValueError``.

        Return:
            ``value`` parameter converted to URL type, or ``None`` if unable
            to parse
        """
        return _try_convert(cls.key_to_url, value)

    @classmethod
    @abc.abstractmethod
    def key_to_url(cls, key: KeyType) -> UrlType:
        """Convert ``key`` to URL

        Raises:
            :exc:`Exception`: the implementation should pass validation related errors
                (:exc:`TypeError`, :exc:`ValueError` etc.) as is.
        """
        raise NotImplementedError()  # pragma: no cover

    @classmethod
    @abc.abstractmethod
    def url_to_key(cls, url: UrlType) -> KeyType:
        """Convert ``url`` to key


        Raises:
            :exc:`Exception`: the implementation should pass validation related errors
                (:exc:`TypeError`, :exc:`ValueError` etc.) as is.
        """
        raise NotImplementedError()  # pragma: no cover

    @classmethod
    def __modify_href_schema__(
        cls,
        schema: typing.MutableMapping[str, typing.Any],
        field: "pydantic.fields.ModelField",
    ):
        """Modify schema of :class:`Href` to this type

        The default implementation reads the return type annotation of
        :meth:`key_to_url()`, and uses its schema as ``Href`` schema.

        Arguments:
            schema: the schema being modified
            field: the ``pydantic`` ``ModelField`` object of the ``Href``
        """
        del field  # unused
        annotation = _get_return_annotation(cls.key_to_url)
        schema_model: typing.Type[pydantic.BaseModel] = pydantic.create_model(
            "schema_model", __root__=(annotation, ...)
        )
        new_schema = schema_model.schema()
        # remove properties pydantic populates by default
        for key_to_remove in "allOf", "$ref":
            schema.pop(key_to_remove, None)
        # retain the original title
        new_schema.pop("title", None)
        schema.update(new_schema)


ReferrableType = typing.TypeVar(  # pylint: disable=invalid-name
    "ReferrableType", bound=Referrable
)


class Href(typing.Generic[ReferrableType]):
    """Hypertext reference to another model

    The class is generic and can be annotated by a type implementing the
    :class:`Referrable` ABC.  If ``Book`` is assumed to be a type implementing
    :class:`Referrable`, then ``Href[Book]`` represents a hyperlink to a book.

    The annotations are compatible with pydantic and allow it to know what kind
    of reference it is working with (see :ref:`quickstart`).
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

    def __eq__(self, other):
        return (
            isinstance(other, Href)
            and self._key == other._key
            and self._url == other._url
        )

    def __hash__(self):
        return hash((Href, self._key, self._url))

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
    def validate(cls, value, field: "pydantic.fields.ModelField"):
        """Parse ``value`` into hyperlink

        This method is mainly intended for the pydantic integration. A user rarely
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
          :exc:`TypeError`: If the :class:`Href` model isn't properly annotated, or if
            ``value`` doesn't conform to any of the recognized types
        """
        if not field.sub_fields:
            raise TypeError("Expected sub field")
        model_type: typing.Type[ReferrableType] = field.sub_fields[0].type_
        if isinstance(value, cls):
            return value
        if isinstance(value, model_type):
            key = value.get_key()
            return cls._from_key(key, model_type)
        key = model_type.parse_as_key(value)
        if key is not None:
            return cls._from_key(key, model_type)
        url = model_type.parse_as_url(value)
        if url is not None:
            return cls._from_url(url, model_type)
        raise TypeError(f"Could not convert {value!r} to href")

    @staticmethod
    def __modify_schema__(
        schema: typing.MutableMapping[str, typing.Any],
        field: typing.Optional["pydantic.fields.ModelField"] = None,
    ):
        if field and field.sub_fields:
            referred: typing.Type[ReferrableType] = field.sub_fields[0].type_
            referred.__modify_href_schema__(schema, field)

    @classmethod
    def _from_key(cls, key: KeyType, model_type: typing.Type[ReferrableType]):
        return cls(key=key, url=model_type.key_to_url(key))

    @classmethod
    def _from_url(cls, url: UrlType, model_type: typing.Type[ReferrableType]):
        return cls(key=model_type.url_to_key(url), url=url)


try:
    from pydantic.json import ENCODERS_BY_TYPE
except ImportError:  # pragma: no cover
    warnings.warn(
        "Failed to add Href encoder. This may affect serializing Href instances to json.",
        ImportWarning,
    )
else:
    ENCODERS_BY_TYPE[Href] = operator.attrgetter("url")
