"""Internal utilities"""

import operator
import typing

import pydantic

T = typing.TypeVar("T")


def is_pydantic_2():
    """Return ``True`` if ``pydantic`` version is 2 or greater"""
    version = getattr(pydantic, "__version__", "1").split(".", 1)
    return int(version[0]) >= 2


class TypeParser(typing.Generic[T]):
    """Adapter over pydantic type parsing

    This class is meant to abstract away details of pydantic type parsing, as
    well as act as a compatibility layer between different major versions.
    """

    def __init__(self, type_: typing.Type[T]):
        """Create type parser over ``type_``"""
        self._type = type_
        self._model = pydantic.create_model("_model", root=(type_, ...))

    def get_type(self) -> typing.Type[T]:
        """Get the underlying type"""
        return self._type

    def parse(self, value: typing.Any) -> T:
        """Parse ``value`` into the underlying type"""
        parsed_value = self._model(root=value)
        return getattr(parsed_value, "root")

    def try_parse(self, value: typing.Any) -> typing.Optional[T]:
        """Similar to :func:`parse()`, but returns ``None`` instead of throwing exception of failure"""
        try:
            return self.parse(value)
        except pydantic.ValidationError:
            return None

    def update_forward_refs(self, **localns: typing.Any):
        """Update forward references"""
        if not is_pydantic_2():
            self._model.update_forward_refs(**localns)

    def to_hypothesis_strategy(self, st):
        """Return hypothesis strategy for the underlying type"""
        return st.from_type(self._model).map(operator.attrgetter("root"))


_URL_PARSER = TypeParser(pydantic.AnyHttpUrl)


def parse_url(value: typing.Any) -> pydantic.AnyHttpUrl:
    """Parse ``value`` as URL"""
    return _URL_PARSER.parse(value)


def try_parse_url(value: typing.Any) -> typing.Optional[pydantic.AnyHttpUrl]:
    """Try parse ``value`` as URL"""
    return _URL_PARSER.try_parse(value)


if is_pydantic_2():

    def get_model_config(model_cls: typing.Type[pydantic.BaseModel], config: str):
        """Get model config, or ``None`` if ``config`` does not exist"""
        assert hasattr(model_cls, "model_config")
        return model_cls.model_config.get(config)

else:

    def get_model_config(model_cls: typing.Type[pydantic.BaseModel], config: str):
        """Get model config, or ``None`` if ``config`` does not exist"""
        assert hasattr(model_cls, "__config__")
        return getattr(model_cls.__config__, config, None)
