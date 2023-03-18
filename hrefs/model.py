"""Referrable models base

The models defined in this module are the basic building blocks of referrable
types. Integration to particular frameworks are defined in the framework
specific module.
"""

import abc
import contextlib
import contextvars
import typing

import pydantic
import pydantic.typing
import typing_extensions

from .href import Href, Referrable
from .errors import ReferrableModelError

_DEFAULT_KEY = "id"

_URL_MODEL: typing.Type[pydantic.BaseModel] = pydantic.create_model(
    "_URL_MODEL", __root__=(pydantic.AnyHttpUrl, ...)
)


def _unwrap_key(obj: typing.Any):
    while isinstance(obj, Href):
        obj = obj.key
    return obj


def _getattr_and_maybe_unwrap_key(obj: typing.Any, name: str, unwrap_key: bool):
    ret = getattr(obj, name)
    if unwrap_key:
        ret = _unwrap_key(ret)
    return ret


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
    """Annotation declaring a field in :class:`BaseReferrableModel` as a primary key

    ``PrimaryKey`` can be used the following way:

    .. code-block:: python

       from typing import Annotation

       class MyModel(BaseReferrableModel):
           my_id: Annotated[int, PrimaryKey]

           # ...the rest of the definitions...

    See :ref:`configure_key` for more details.

    Arguments:
        type_: The underlying key type if the annotated primary key is
               itself a hyperlink. See :ref:`href_as_key`.
        name: The name of the key. It may be distinct from the actual field
              name, and will be used to match the key to path/query parameters
    """

    __slots__ = ["type_", "name"]

    def __init__(
        self,
        type_: typing.Optional[typing.Type] = None,
        name: typing.Optional[str] = None,
    ):
        self.type_ = type_
        self.name = name


class _ReferrableModelKeyInfo(typing.NamedTuple):
    key_type: typing.Type
    should_unwrap_key: bool
    field_name: str


class _ReferrableModelMeta(pydantic.main.ModelMetaclass):
    def __new__(cls, name, bases, namespace, **kwargs):
        annotations = pydantic.typing.resolve_annotations(
            namespace.get("__annotations__", {}), namespace.get("__module__", None)
        )
        key_names, key_infos = cls._create_key_names_and_types(name, annotations)
        assert len(key_names) == len(key_infos)

        if key_infos or not cls._has_referrable_model_base(bases):
            if len(key_infos) == 1:
                (
                    key_model,
                    get_key,
                ) = cls._create_key_converters_single_type(key_infos[0])

            else:
                (
                    key_model,
                    get_key,
                ) = cls._create_key_converters_multiple_types(key_names, key_infos)

            namespace["_key_names"] = tuple(key_names)
            namespace["_key_model"] = key_model
            namespace["_get_key"] = get_key
            namespace["_key_map"] = {}

        return super().__new__(cls, name, bases, namespace, **kwargs)

    def __init__(cls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cls._calculate_key_map()

    @classmethod
    def _has_referrable_model_base(cls, bases):
        return any(isinstance(base, cls) for base in bases)

    @staticmethod
    def _create_key_names_and_types(
        name: str, all_annotations: typing.Mapping[str, typing.Any]
    ):
        key_names: typing.List[str] = []
        key_infos: typing.List[_ReferrableModelKeyInfo] = []
        for field_name, annotation in all_annotations.items():
            if typing_extensions.get_origin(annotation) is typing_extensions.Annotated:
                annotations = typing_extensions.get_args(annotation)
                key_annotations = [
                    key
                    for key in annotations
                    if key is PrimaryKey or isinstance(key, PrimaryKey)
                ]
                n_key_annotations = len(key_annotations)
                if n_key_annotations > 1:
                    raise ReferrableModelError(
                        f"{name}.{field_name}: Expected zero or one PrimaryKey annotations,"
                        f" got {n_key_annotations}"
                    )
                if n_key_annotations == 1:
                    origin_type = annotations[0]
                    primary_key_annotation: PrimaryKey = key_annotations[0]
                    # convert class into default instance
                    if primary_key_annotation is PrimaryKey:
                        primary_key_annotation = PrimaryKey()
                    type_from_annotation = primary_key_annotation.type_
                    key_name_from_annotation = primary_key_annotation.name
                    key_type = type_from_annotation or origin_type
                    should_unwrap_key = (
                        typing_extensions.get_origin(origin_type) is Href
                        and type_from_annotation is not None
                    )
                    key_names.append(key_name_from_annotation or field_name)
                    key_infos.append(
                        _ReferrableModelKeyInfo(key_type, should_unwrap_key, field_name)
                    )
        if not key_names and _DEFAULT_KEY in all_annotations:
            key_names.append(_DEFAULT_KEY)
            key_infos.append(
                _ReferrableModelKeyInfo(
                    all_annotations[_DEFAULT_KEY], False, _DEFAULT_KEY
                )
            )
        return key_names, key_infos

    @classmethod
    def _create_key_converters_multiple_types(
        cls,
        key_names: typing.Iterable[str],
        key_infos: typing.Iterable[_ReferrableModelKeyInfo],
    ):
        key_type = typing.NamedTuple(  # type: ignore
            "key",
            [
                (key_name, key_info.key_type)
                for (key_name, key_info) in zip(key_names, key_infos)
            ],
        )
        key_model = cls._create_key_model(key_type)

        def get_key(self):
            return key_model(
                __root__=[
                    _getattr_and_maybe_unwrap_key(
                        self, key_info.field_name, key_info.should_unwrap_key
                    )
                    for key_name, key_info in zip(key_names, key_infos)
                ]
            ).__root__

        return key_model, get_key

    @classmethod
    def _create_key_converters_single_type(cls, key_info: _ReferrableModelKeyInfo):
        key_model = cls._create_key_model(key_info.key_type)

        def get_key(self):
            return key_model(
                __root__=_getattr_and_maybe_unwrap_key(
                    self, key_info.field_name, key_info.should_unwrap_key
                )
            ).__root__

        return key_model, get_key

    @staticmethod
    def _create_key_model(key_type: typing.Type):
        return pydantic.create_model("key_model", __root__=(key_type, ...))


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
    use a :class:`HrefResolver` provided by the web framework integration.

    Subclassing or initializing instances of a subclass raises
    :exc:`hrefs.ReferrableModelError` in case the library detects the model is
    incorrectly configured.
    """

    _key_model: typing.ClassVar[typing.Type[pydantic.BaseModel]]
    _key_names: typing.ClassVar[typing.Tuple[str, ...]]
    _get_key: typing.ClassVar[typing.Callable[["BaseReferrableModel"], typing.Any]]
    _key_map: typing.ClassVar[
        typing.Dict[str, typing.Union[str, typing.Tuple[str, ...]]]
    ]

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
        return cls._try_parse_as(cls._key_model, value)

    @classmethod
    def parse_as_url(cls, value: typing.Any) -> typing.Optional[pydantic.AnyHttpUrl]:
        """Parse ``value`` as an URL (a :class:`pydantic.AnyHttpUrl` instance)"""
        return cls._try_parse_as(_URL_MODEL, value)

    @classmethod
    def has_simple_key(cls) -> bool:
        """Query if the model has a simple key

        Returns:
            ``True`` if the model has simple (single part) key, ``False``
            otherwise
        """
        return len(cls._key_names) == 1

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
        if cls.has_simple_key():
            key = (key,)
        params = {}
        for subkeys, subkey_names in zip(key, cls._key_map.values()):
            subkeys = _unwrap_key(subkeys)
            if isinstance(subkey_names, str):
                params[subkey_names] = subkeys
            else:
                for subkey_name, subkey in zip(subkey_names, subkeys):
                    params[subkey_name] = subkey
        return params

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
        subkeys = []
        try:
            for subkey_names in cls._key_map.values():
                if isinstance(subkey_names, str):
                    subkey = params[subkey_names]
                else:
                    subkey = [params[subkey_name] for subkey_name in subkey_names]
                subkeys.append(subkey)
        except KeyError as ex:
            missing_keys = set(cls._key_map.keys()) - set(params.keys())
            raise ValueError(
                f"Could not convert {params} to key of {cls.__name__}. "
                f"Missing the following params: {', '.join(missing_keys)}"
            ) from ex
        if cls.has_simple_key():
            subkeys = subkeys[0]
        return cls._parse_as(cls._key_model, subkeys)

    @classmethod
    def update_forward_refs(cls, **localns: typing.Any) -> None:
        super().update_forward_refs(**localns)
        cls._key_model.update_forward_refs(**localns)
        cls._calculate_key_map()

    @staticmethod
    def _parse_as(model: typing.Type[pydantic.BaseModel], value: typing.Any):
        parsed_value = model.parse_obj(value)
        return getattr(parsed_value, "__root__")

    @classmethod
    def _try_parse_as(
        cls, model: typing.Type[pydantic.BaseModel], value: typing.Any
    ) -> typing.Optional[typing.Any]:
        try:
            return cls._parse_as(model, value)
        except pydantic.ValidationError:
            return None

    @classmethod
    def _calculate_key_map(cls) -> None:
        if not cls._key_names:
            return

        key_type = cls._key_model.__fields__["__root__"].outer_type_
        key_types: typing.Dict[str, typing.Type]
        if cls.has_simple_key():
            key_name = cls._key_names[0]
            key_types = {key_name: key_type}
        else:
            key_types = key_type.__annotations__

        cls._key_map.clear()
        for key_name, key_type in key_types.items():
            target_key_name: typing.Union[str, typing.Tuple[str, ...]] = key_name
            # If key part is `Href`, we examine the target and unwrap it
            if typing_extensions.get_origin(key_type) is Href:
                (target_type,) = typing_extensions.get_args(key_type)
                target_type_key_map = getattr(target_type, "_key_map", None)
                if target_type_key_map:
                    target_type_key_names = target_type_key_map.values()
                    # This would get complicated: if the target of `Href` also
                    # has complex key that needs unwrapping (indirection two
                    # levels deep), we don't do that. It would be possible if
                    # calculating key map was properly recursive, though.
                    if not all(isinstance(name, str) for name in target_type_key_names):
                        raise ReferrableModelError(
                            f"Model {cls.__name__} href key {key_name} has too many levels of indirection. "
                            f"{target_type!r} has key map {target_type_key_map!r}"
                        )
                    target_key_name_list = [
                        f"{key_name}_{target_key_name}"
                        for target_key_name in target_type_key_map.values()
                    ]
                    target_key_name = (
                        tuple(target_key_name_list)
                        if len(target_key_name_list) > 1
                        else target_key_name_list[0]
                    )
            cls._key_map[key_name] = target_key_name
