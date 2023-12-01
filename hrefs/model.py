"""Referrable models base

The models defined in this module are the basic building blocks of referrable
types. Integration to particular frameworks are defined in the framework
specific module.
"""

import abc
import contextlib
import contextvars
from dataclasses import dataclass
import functools
import typing

import pydantic
import pydantic.typing
import typing_extensions

from .href import Href, Referrable
from .errors import ReferrableModelError
from ._util import TypeParser, is_pydantic_2, try_parse_url

_DEFAULT_KEY = "id"


def _unwrap_key(obj: typing.Any):
    while isinstance(obj, Href):
        obj = obj.key
    if isinstance(obj, tuple):
        return tuple(_unwrap_key(part) for part in obj)
    return obj


def _getattr_and_maybe_unwrap_key(obj: typing.Any, *, name: str, unwrap_key: bool):
    # return _unwrap_key(getattr(obj, name))
    obj = getattr(obj, name)
    if unwrap_key:
        obj = _unwrap_key(obj)
    return obj


@dataclass
class _KeyPartSpec:
    field_name: str
    key_name: str
    is_href_with_forward_reference: bool
    key_parts_specs: typing.Optional[typing.Tuple["_KeyPartSpec", ...]]


_KeySpecs = typing.Tuple[_KeyPartSpec, ...]


def _convert_key_to_params(
    key: typing.Union[typing.Any, typing.Tuple[typing.Any, ...]],
    key_specs: _KeySpecs,
    *,
    prefix="",
):
    params = {}
    if len(key_specs) == 1:
        key = (key,)
    for key_part, key_spec in zip(key, key_specs):
        key_name = f"{prefix}{key_spec.key_name}"
        if key_spec.key_parts_specs:
            next_params = _convert_key_to_params(
                key_part, key_spec.key_parts_specs, prefix=f"{key_name}_"
            )
            params.update(next_params)
        else:
            params[key_name] = key_part
    return params


def _convert_params_to_key(
    params: typing.Mapping[str, typing.Any],
    key_specs: _KeySpecs,
    *,
    cls: typing.Type[typing.Any],
    prefix="",
):
    key_parts = []
    for key_spec in key_specs:
        key_name = f"{prefix}{key_spec.key_name}"
        if key_spec.key_parts_specs:
            next_key_part = _convert_params_to_key(
                params,
                key_spec.key_parts_specs,
                cls=cls,
                prefix=f"{key_name}_",
            )
            key_parts.append(next_key_part)
        else:
            try:
                key_parts.append(params[key_name])
            except KeyError as ex:
                raise ValueError(
                    f"Cannot convert parameters {params!r} to a hyperlink to {cls.__name__}. Missing: {key_name}"
                ) from ex
    if len(key_specs) == 1:
        return key_parts[0]
    return tuple(key_parts)


class HrefResolver(typing_extensions.Protocol):
    """Hyperlink resolver for :class:`BaseReferrableModel` subclasses

    A hyperlink resolver acts as an integration point between models and the web
    framework.  A web framework implements its resolver that encapsulates the
    general logic of converting between keys and URLs.  A model that subclasses
    :class:`BaseReferrableModel` then uses the visitor pattern on the
    implemented methods to resolve keys and URLs.

    A user of the ``hrefs`` library rarely needs to concern themselves with this
    class.  It is meant as a protocol to be implemented by new web framework
    integrations.

    .. seealso::

       :func:`resolve_hrefs()` that is used to inject the active resolver context
    """

    @abc.abstractmethod
    def key_to_url(
        self, key: typing.Any, *, model_cls: typing.Type["BaseReferrableModel"]
    ) -> pydantic.AnyHttpUrl:
        """Convert key to url

        Arguments:
            key: The key to convert. The type of the key is assumed to be the key
                 type of ``model_cls``.
            model_cls: The model class performing the conversion

        Returns:
            The URL parsed from ``key``

        Raises:
            :exc:`hrefs.ReferrableModelError`: if the model is incorrectly configured
            :exc:`Exception`: validation errors when converting ``key`` are passed as is
        """
        raise NotImplementedError()  # pragma: no cover

    @abc.abstractmethod
    def url_to_key(
        self, url: pydantic.AnyHttpUrl, *, model_cls: typing.Type["BaseReferrableModel"]
    ) -> typing.Any:
        """Convert url to key

        Arguments:
            url: The url to convert. The structure is assumed to follow the URL
                 structure of ``model_cls``.
            model_cls: The model class performing the conversion

        Returns:
            The key parsed from ``url``

        Raises:
            :exc:`hrefs.ReferrableModelError`: if the model is incorrectly configured
            :exc:`Exception`: validation errors when converting ``url`` are passed as is
        """
        raise NotImplementedError()  # pragma: no cover


_href_resolver_var: contextvars.ContextVar[HrefResolver] = contextvars.ContextVar(
    "_href_resolver_var"
)


if typing.TYPE_CHECKING:  # pragma: no cover
    HrefResolverVar = typing.TypeVar("HrefResolverVar", bound=HrefResolver)

    def resolve_hrefs(
        href_resolver: HrefResolverVar,
    ) -> typing.ContextManager[HrefResolverVar]:
        """resolve_hrefs() for mypy"""
        del href_resolver

else:

    @contextlib.contextmanager
    def resolve_hrefs(href_resolver: HrefResolver):
        """Context manager that sets the active hyperlink resolver

        Makes ``href_resolver`` responsible for converting between keys and URLs
        for subclasses of :class:`BaseReferrableModel`.  Any conversion must
        happen inside the context.

        .. code-block:: python

           from hrefs.model import BaseReferrableModel, HrefResolver, resolve_hrefs

           class Book(BaseReferrableModel):
               id: int

           class MyHrefResolver(HrefResolver):
               ...

           with resolve_hrefs(MyHrefResolver(...)) as href_resolver:
               # uses ``href_resolver`` to convert between keys and URLs
               pydantic.parse_obj_as(Href[Book], "http://example.com/books/1")
               pydantic.parse_obj_as(Href[Book], 1)

           # raises error
           pydantic.parse_obj_as(Href[Book], "http://example.com/books/1")
           pydantic.parse_obj_as(Href[Book], 1)

        This function is intended for web integration developers.  The
        integrations provide more user friendly ways to expose the resolution
        functionality, for example `hrefs.starlette.HrefMiddleware` for
        Starlette/FastAPI integration.

        Arguments:
            href_resolver: The hyperlink resolver to activate
        """
        token = _href_resolver_var.set(href_resolver)
        try:
            yield href_resolver
        finally:
            _href_resolver_var.reset(token)


class PrimaryKey:
    """Declare a field in :class:`BaseReferrableModel` as the primary key

    ``PrimaryKey`` can be used the following way:

    .. code-block:: python

       from typing import Annotation

       class MyModel(BaseReferrableModel):
           my_id: Annotated[int, PrimaryKey]

           # ...the rest of the definitions...

    See :ref:`configure_key` for more details.

    Arguments:
        type_: The underlying key type. This parameter is only used when the key part
               is a hyperlink whose target is a forward reference. See :ref:`href_as_key`.
        name: The name of the key. This can be used to override the name of the key part
              (that normally defaults to the field name).
    """

    __slots__ = ["type_", "name"]

    def __init__(
        self,
        type_: typing.Optional[typing.Type] = None,
        name: typing.Optional[str] = None,
    ):
        self.type_ = type_
        self.name = name


if typing.TYPE_CHECKING or is_pydantic_2():
    from pydantic._internal._model_construction import ModelMetaclass as _ModelMetaclass
else:
    from pydantic.main import (  # pylint: disable=no-name-in-module
        ModelMetaclass as _ModelMetaclass,
    )


class _ReferrableModelMeta(_ModelMetaclass):
    def __new__(cls, name, bases, namespace, *args, **kwargs):
        if is_pydantic_2():
            annotations = namespace.get("__annotations__", {})
        else:
            annotations = (
                pydantic.typing.resolve_annotations(  # pylint: disable=no-member
                    namespace.get("__annotations__", {}),
                    namespace.get("__module__", None),
                )
            )

        key_parts_with_annotation_info = cls._get_key_info_from_annotations(
            annotations, name=name
        )
        key_types_and_specs = [
            cls._get_key_types_and_specs(
                field_name, key_part_type, key_metadata, name=name
            )
            for (
                field_name,
                key_part_type,
                key_metadata,
            ) in key_parts_with_annotation_info
        ]

        if key_types_and_specs or not cls._has_referrable_model_base(bases):
            if key_types_and_specs:
                key_types, key_specs = [list(k) for k in zip(*key_types_and_specs)]
            else:
                key_types, key_specs = [], []

            key_parser = cls._get_key_parser_from_types(key_types, key_specs)
            get_key = cls._get_key_getter_from_specs(key_specs, key_parser.get_type())

            namespace["_key_parser"] = key_parser
            namespace["_key_specs"] = tuple(key_specs)
            namespace["_get_key"] = get_key

        return super().__new__(cls, name, bases, namespace, *args, **kwargs)

    @staticmethod
    def _get_key_info_from_annotations(
        annotations: typing.Mapping[str, typing.Any], *, name: str
    ):
        key_parts = []
        for field_name, annotation in annotations.items():
            if typing_extensions.get_origin(annotation) is typing_extensions.Annotated:
                annotation_args = typing_extensions.get_args(annotation)
                key_annotations = [
                    key
                    for key in annotation_args
                    if key is PrimaryKey or isinstance(key, PrimaryKey)
                ]
                n_key_annotations = len(key_annotations)
                if n_key_annotations > 1:
                    raise ReferrableModelError(
                        f"{name}.{field_name}: Expected zero or one PrimaryKey annotations,"
                        f" got {n_key_annotations}"
                    )
                if n_key_annotations == 1:
                    field_type = annotation_args[0]
                    primary_key_annotation: PrimaryKey = key_annotations[0]
                    # convert class into default instance
                    if primary_key_annotation is PrimaryKey:
                        primary_key_annotation = PrimaryKey()
                    key_parts.append((field_name, field_type, primary_key_annotation))
        if not key_parts and _DEFAULT_KEY in annotations:
            key_parts.append((_DEFAULT_KEY, annotations[_DEFAULT_KEY], PrimaryKey()))
        return key_parts

    @staticmethod
    def _get_key_types_and_specs(
        field_name: str,
        key_part_type: typing.Type[typing.Any],
        key_metadata: PrimaryKey,
        *,
        name: str,
    ):
        actual_key_part_type = key_part_type
        key_name = key_metadata.name or field_name
        key_parts_specs = None
        is_href_with_forward_reference = False
        key_part_type_origin = typing_extensions.get_origin(key_part_type)
        if key_part_type_origin is Href:
            (target_type,) = typing_extensions.get_args(key_part_type)
            if isinstance(target_type, typing.ForwardRef):
                if not key_metadata.type_:
                    raise ReferrableModelError(
                        f"{name}.{field_name} is hyperlink with forward reference (has type {key_part_type}). "
                        "Setting type_ in primary key annotation required."
                    )
                actual_key_part_type = key_metadata.type_
                is_href_with_forward_reference = True
            else:
                key_parts_specs = (
                    target_type._get_key_specs()  # pylint: disable=protected-access
                )
        return actual_key_part_type, _KeyPartSpec(
            field_name=field_name,
            key_name=key_name,
            key_parts_specs=key_parts_specs,
            is_href_with_forward_reference=is_href_with_forward_reference,
        )

    @staticmethod
    def _get_key_parser_from_types(
        types: typing.Sequence[typing.Type[typing.Any]],
        key_specs: typing.Sequence[_KeyPartSpec],
    ):
        if len(types) == 1:
            return TypeParser(types[0])
        tuple_type = typing.NamedTuple(  # type: ignore
            "key",
            [(key_spec.key_name, type_) for (key_spec, type_) in zip(key_specs, types)],
        )
        return TypeParser(tuple_type)

    @staticmethod
    def _get_key_getter_from_specs(
        key_specs: typing.Sequence[_KeyPartSpec], key_type: typing.Type[typing.Any]
    ):
        if len(key_specs) == 1:
            getter = functools.partial(
                _getattr_and_maybe_unwrap_key,
                name=key_specs[0].field_name,
                unwrap_key=key_specs[0].is_href_with_forward_reference,
            )

            def get_key(self):
                return getter(self)

        else:
            getters = [
                functools.partial(
                    _getattr_and_maybe_unwrap_key,
                    name=key_spec.field_name,
                    unwrap_key=key_spec.is_href_with_forward_reference,
                )
                for key_spec in key_specs
            ]

            def get_key(self):
                return key_type(*(getter(self) for getter in getters))

        return get_key

    @classmethod
    def _has_referrable_model_base(cls, bases):
        return any(isinstance(base, cls) for base in bases)


class BaseReferrableModel(
    pydantic.BaseModel, Referrable, metaclass=_ReferrableModelMeta
):
    """Referrable pydantic model

    A subclass of both :class:`pydantic.BaseModel` and
    :class:`hrefs.Referrable`.  It should be used as the base class of any
    pydantic model that will be used as a target of :class:`hrefs.Href`.

    ``BaseReferrableModel`` provides implementations of :func:`get_key()` and
    :func:`parse_as_key()` based on field annotations.  By default, the model
    key is the ``id`` field (if it exists), but that can be changed by using
    :class:`PrimaryKey` to annotate other field or fields.

    ``BaseReferrableModel`` intentionally has tight coupling to the `pydantic
    <https://pydantic-docs.helpmanual.io/>`_ library.  As such, it relies
    heavily on the facilities of that library to handle annotations and parsing.
    The URL type of pydantic based referrable models is always
    :class:`pydantic.AnyHttpUrl`.

    While the model class knows how to extract key types from annotations, it
    doesn't know how to convert between keys and URLs.  For that, it needs to
    use a :class:`model.HrefResolver` provided by the web framework integration.

    Subclassing or initializing instances of a subclass raises
    :exc:`hrefs.ReferrableModelError` in case the library detects the model is
    incorrectly configured.
    """

    _key_specs: typing.ClassVar[_KeySpecs]
    _key_parser: typing.ClassVar[TypeParser[typing.Any]]
    _get_key: typing.ClassVar[typing.Callable[["BaseReferrableModel"], typing.Any]]

    def get_key(self) -> typing.Any:
        """Return the model key

        Returns:
            The model key based on the field annotations. If the key is
            composite, returns a tuple containing the parts.
        """
        return self._get_key()

    @classmethod
    def key_to_url(cls, key) -> pydantic.AnyHttpUrl:
        """Convert ``key`` to URL

        Uses the web framework specific resolution logic to convert the model
        key to URL (a :class:`pydantic.AnyHttpUrl` instance).

        Raises:
            :exc:`hrefs.ReferrableModelError`: if the model is incorrectly configured
            :exc:`Exception`: validation errors when converting ``key`` are passed as is
        """
        resolver = _href_resolver_var.get()
        return resolver.key_to_url(key, model_cls=cls)

    @classmethod
    def url_to_key(cls, url: pydantic.AnyHttpUrl) -> typing.Any:
        """Convert ``url`` to model key

        Uses the web framework specific resolution logic to convert an URL
        to the model key based on field annotations.

        Raises:
            :exc:`hrefs.ReferrableModelError`: if the model is incorrectly configured
            :exc:`Exception`: validation errors when converting ``url`` are passed as is
        """
        resolver = _href_resolver_var.get()
        return resolver.url_to_key(url, model_cls=cls)

    @classmethod
    def parse_as_key(cls, value: typing.Any) -> typing.Optional[typing.Any]:
        """Parse ``value`` as a model key

        The type of the model key is based on the field annotations.  Either a
        single type, or (in the case of a composite key), a tuple of the parts.
        """
        return cls._key_parser.try_parse(value)

    @classmethod
    def parse_as_url(cls, value: typing.Any) -> typing.Optional[pydantic.AnyHttpUrl]:
        """Parse ``value`` as an URL (a :class:`pydantic.AnyHttpUrl` instance)"""
        return try_parse_url(value)

    @classmethod
    def has_simple_key(cls) -> bool:
        """Query if the model has a simple key

        Returns:
            ``True`` if the model has simple (single part) key, ``False``
            otherwise
        """
        return len(cls._key_specs) == 1

    @classmethod
    def key_to_params(cls, key: typing.Any) -> typing.Dict[str, typing.Any]:
        """Convert model key to path/query parameters of an URL

        This is a helper that can be used to convert a model key into a
        dictionary containing the key parts.  Hyperlinks are unwrapped (see
        :ref:`href_as_key`).  The dictionary can be used to generate the path
        and query parameters of URLs in a typical HTTP framework.

        Arguments:
            key: model key

        Returns:
            A dictionary mapping key names to key parts
        """
        return _convert_key_to_params(_unwrap_key(key), cls._key_specs)

    @classmethod
    def params_to_key(cls, params: typing.Mapping[str, typing.Any]) -> typing.Any:
        """Convert path/query parameters of an URL to model key

        This helper can be used to convert a parameter mapping to model
        key. It is the inverse of :meth:`key_to_params()`.

        Arguments:
            params: A mapping from key names to key parts

        Returns:
            Model key parsed from ``params``

        Raises:
           :exc:`ValueError`: if ``params`` does not contain sufficient elements
             to construct the key
        """
        key_parts = _convert_params_to_key(params, cls._key_specs, cls=cls)
        return cls._key_parser.parse(key_parts)

    @classmethod
    def update_forward_refs(cls, **localns: typing.Any) -> None:
        super().update_forward_refs(**localns)
        cls._key_parser.update_forward_refs(**localns)

    @classmethod
    def _get_key_specs(cls) -> _KeySpecs:
        return cls._key_specs


if typing.TYPE_CHECKING or is_pydantic_2():

    class HrefsConfigDict(pydantic.ConfigDict):
        """Typed dict that extends ``pydantiuc.ConfigDict`` with configurations used for :class:`BaseReferrableModel`"""

        details_view: str
        """Name of a view used by web framework integration"""

else:

    class HrefsConfigDict(typing.TypedDict):
        """Typed dict that extends ``pydantiuc.ConfigDict`` with configurations used for :class:`BaseReferrableModel`"""

        details_view: str
        """Name of a view used by web framework integration"""
