"""Base models for referring and referrable types"""

import typing

import pydantic
import pydantic.typing
import typing_extensions

from .href import Referrable

_DEFAULT_KEY = "id"

T = typing.TypeVar("T")


class PrimaryKey:
    """Annotation declaring a field in :class:`BaseReferrableModel` as key

    ``PrimaryKey`` can be used the following way:

    .. code-block:: python

       from typing import Annotation

       class MyModel(BaseReferrableModel):
           my_id: Annotated[int, PrimaryKey]

           # ...the rest of the definitions...

    See :ref:`configure_key` for more details.
    """


# mypy doesn't like dynamic base classes:
# https://github.com/python/mypy/wiki/Unsupported-Python-Features
# ...so working around by some dirty casts
_base1: typing.Any = type(pydantic.BaseModel)
_base2: typing.Any = type(Referrable)


# pylint: disable=duplicate-bases,inconsistent-mro
class _ReferrableModelMeta(_base1, _base2):
    def __new__(cls, name, bases, namespace, **kwargs):
        key_names = []
        key_types = []
        all_annotations = pydantic.typing.resolve_annotations(
            namespace.get("__annotations__", {}), namespace.get("__module__", None)
        )
        for key_name, annotation in all_annotations.items():
            if typing_extensions.get_origin(annotation) is typing_extensions.Annotated:
                annotations = typing_extensions.get_args(annotation)
                key_annotations = [key for key in annotations if key is PrimaryKey]
                n_key_annotations = len(key_annotations)
                if n_key_annotations > 1:
                    raise TypeError(
                        f"{name}.{key_name}: Expected zero or one PrimaryKey annotations,"
                        f" got {n_key_annotations}"
                    )
                if n_key_annotations == 1:
                    key_names.append(key_name)
                    key_types.append(annotations[0])
        if not key_names and _DEFAULT_KEY in all_annotations:
            key_names.append(_DEFAULT_KEY)
            key_types.append(all_annotations[_DEFAULT_KEY])
        assert len(key_names) == len(key_types)

        if key_types:
            if len(key_types) > 1:
                key_type = typing.NamedTuple(
                    f"{name}_key", list(zip(key_names, key_types))
                )

                def get_key(self):
                    # pylint: disable=no-member
                    return key_type._make(getattr(self, k) for k in key_names)

            else:
                key_name = key_names[0]
                key_type = key_types[0]

                def get_key(self):
                    return getattr(self, key_name)

            namespace["_key_names"] = tuple(key_names)
            namespace["_key_type"] = key_type
            namespace["_get_key"] = get_key

        return super().__new__(cls, name, bases, namespace, **kwargs)


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

    _key_names: typing.ClassVar[typing.Tuple[str]]

    def get_key(self) -> typing.Any:
        """Return the model key

        Returns:
            The model key based on the field annotations. If the key is
            composite, return a tuple containing the parts.
        """
        return self._get_key()  # type: ignore

    @staticmethod
    def try_parse_as(type_: typing.Type[T], value: typing.Any) -> typing.Optional[T]:
        """Like ``pydantic.parse_obj_as()`` except return ``None`` on validation error

        Arguments:
            type_: the type parsed to
            value: the value to parse

        Returns:
            ``value`` parsed as type ``type_``, or ``None`` on validation error
        """
        try:
            return pydantic.parse_obj_as(type_, value)
        except pydantic.ValidationError:
            return None

    @classmethod
    def parse_as_key(cls, value: typing.Any) -> typing.Optional[typing.Any]:
        """Parse ``value`` as the key type

        The type of the model key based on the field annotations. Either a
        single type, or (in case of composite key), a tuple of the parts.
        """
        return cls.try_parse_as(cls._key_type, value)
