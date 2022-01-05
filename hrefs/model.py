"""Base models for referring and referrable types"""

import typing

import pydantic
import pydantic.typing
import typing_extensions

from .href import Href, Referrable

_DEFAULT_KEY = "id"


def _unwrap_key(obj: typing.Any):
    while isinstance(obj, Href):
        obj = obj.key
    return obj


def _getattr_and_maybe_unwrap_key(obj: typing.Any, name: str, unwrap_key: bool):
    ret = getattr(obj, name)
    if unwrap_key:
        ret = _unwrap_key(ret)
    return ret


class PrimaryKey:
    """Annotation declaring a field in :class:`BaseReferrableModel` as key

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
              name, and will appear in path parameters etc.
    """

    __slots__ = ["type_", "name"]

    def __init__(self, type_: typing.Type = None, name: str = None):
        self.type_ = type_
        self.name = name


# mypy doesn't like dynamic base classes:
# https://github.com/python/mypy/wiki/Unsupported-Python-Features
# ...so working around by some dirty casts
_base1: typing.Any = type(pydantic.BaseModel)
_base2: typing.Any = type(Referrable)


class _ReferrableModelKeyInfo(typing.NamedTuple):
    key_type: typing.Type
    should_unwrap_key: bool
    field_name: str


# pylint: disable=duplicate-bases,inconsistent-mro
class _ReferrableModelMeta(_base1, _base2):
    def __new__(cls, name, bases, namespace, **kwargs):
        annotations = pydantic.typing.resolve_annotations(
            namespace.get("__annotations__", {}), namespace.get("__module__", None)
        )
        key_names, key_infos = cls._create_key_names_and_types(name, annotations)
        assert len(key_names) == len(key_infos)

        if key_infos:
            if len(key_infos) > 1:
                (
                    key_model,
                    get_key,
                ) = cls._create_key_converters_multiple_types(key_names, key_infos)

            else:
                (
                    key_model,
                    get_key,
                ) = cls._create_key_converters_single_type(key_infos[0])

            namespace["_key_names"] = tuple(key_names)
            namespace["_key_model"] = key_model
            namespace["_get_key"] = get_key
            namespace["_key_map"] = {}

        return super().__new__(cls, name, bases, namespace, **kwargs)

    def __init__(cls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(cls, "_key_model"):
            cls._calculate_key_map()

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
                    raise TypeError(
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


# pylint: disable=abstract-method
class BaseReferrableModel(
    pydantic.BaseModel, Referrable, metaclass=_ReferrableModelMeta
):
    """Referrable model with pydantic integration

    A subclass of both :class:`pydantic.BaseModel` and
    :class:`hrefs.Referrable`.  It should be used as the base class of any
    pydantic model that will be used as target of :class:`hrefs.Href`.

    ``BaseReferrableModel`` provides implementation on :func:`get_key()` and
    :func:`parse_as_key()` based on its field annotations. By default the model
    key is the ``id`` field (if it exists), but that can be changed by using
    :class:`PrimaryKey` to annotate other field(s).

    When using referrable models with FastAPI or Starlette in particular,
    :class:`hrefs.starlette.ReferrableModel` is more natural base.
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
            composite, return a tuple containing the parts.
        """
        return self._get_key()

    @classmethod
    def has_simple_key(cls) -> bool:
        """Query if the model has a simple key

        Returns:
            ``True`` if the model has simple (single part) key, ``False``
            otherwise
        """
        return len(cls._key_names) == 1

    @classmethod
    def key_to_path_params(cls, key: typing.Any) -> typing.Dict[str, typing.Any]:
        """Convert model key to path parameters

        This is a helper that can be used to convert a model key into a
        dictionary containing the key parts. Hyperlinks are unwrapped (see
        :ref:`href_as_key`).  It can be used to generate URLs in several HTTP
        frameworks.

        Arguments:
            key: model key

        Returns:
            A dictionary mapping key names to key parts

        """
        if cls.has_simple_key():
            key = (key,)
        path_params = {}
        for subkeys, subkey_names in zip(key, cls._key_map.values()):
            subkeys = _unwrap_key(subkeys)
            if isinstance(subkey_names, str):
                path_params[subkey_names] = subkeys
            else:
                for subkey_name, subkey in zip(subkey_names, subkeys):
                    path_params[subkey_name] = subkey
        return path_params

    @classmethod
    def path_params_to_key(
        cls, path_params: typing.Mapping[str, typing.Any]
    ) -> typing.Any:
        """Convert path parameters to model key

        This helper can be used to convert path parameter mapping to model
        key. It is the inverse of :meth:`key_to_path_params()`.

        Arguments:
            path_params: A mapping from key names to key parts

        Returns:
            Model key parsed from ``path_params``
        """
        subkeys = []
        for subkey_names in cls._key_map.values():
            if isinstance(subkey_names, str):
                subkey = path_params[subkey_names]
            else:
                subkey = [path_params[subkey_name] for subkey_name in subkey_names]
            subkeys.append(subkey)
        if cls.has_simple_key():
            subkeys = subkeys[0]
        return cls.parse_as_key(subkeys)

    @staticmethod
    def try_parse_as(
        model: typing.Type[pydantic.BaseModel], value: typing.Any
    ) -> typing.Optional[typing.Any]:
        """Parse ``value`` as ``model`` but swallow validation error

        Arguments:
            model: the model parsed to
            value: the value to parse

        Returns:
            ``value`` parsed as ``model``, or ``None`` on validation error
        """
        try:
            parsed_value = model.parse_obj(value)
        except pydantic.ValidationError:
            return None
        return getattr(parsed_value, "__root__")

    @classmethod
    def parse_as_key(cls, value: typing.Any) -> typing.Optional[typing.Any]:
        """Parse ``value`` as the key type

        The type of the model key based on the field annotations. Either a
        single type, or (in case of composite key), a tuple of the parts.
        """
        return cls.try_parse_as(cls._key_model, value)

    @classmethod
    def update_forward_refs(cls, **localns: typing.Any) -> None:
        super().update_forward_refs(**localns)
        cls._key_model.update_forward_refs(**localns)
        cls._calculate_key_map()

    @classmethod
    def _calculate_key_map(cls):
        key_type = cls._key_model.__fields__["__root__"].outer_type_
        key_types: typing.Dict[str, typing.Type]
        if cls.has_simple_key():
            key_name = cls._key_names[0]
            key_types = {key_name: key_type}
        else:
            key_types = key_type.__annotations__

        cls._key_map.clear()
        for key_name, key_type in key_types.items():
            target_key_name = key_name
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
                        raise TypeError(
                            "Href to models with complex key are not supported as model key. "
                            f"{target_type!r} has key map {target_type_key_map!r}"
                        )
                    target_key_name = [
                        f"{key_name}_{target_key_name}"
                        for target_key_name in target_type_key_map.values()
                    ]
                    target_key_name = (
                        tuple(target_key_name)
                        if len(target_key_name) > 1
                        else target_key_name[0]
                    )
            cls._key_map[key_name] = target_key_name
