"""Hypothesis plugin"""

import inspect
import typing

import pydantic
import typing_extensions
import hypothesis.strategies as st

from .href import Href


def _hrefs_strategy(model_type: typing.Type[Href]):
    args = typing_extensions.get_args(model_type)
    if len(args) != 1:
        raise ValueError("Cannot create strategy for plain Href")
    referrable_type = args[0]
    try:
        key_model = getattr(referrable_type, "_key_model", None)
        if not key_model:
            return_annotation = inspect.signature(
                referrable_type.url_to_key
            ).return_annotation
            key_model = pydantic.create_model(
                "_key_model", __root__=(return_annotation, ...)
            )
    except Exception as ex:
        raise ValueError(
            f"Cannot create strategy for Href[{referrable_type.__name__}]: "
            f"could not determine key model for {referrable_type.__name__ }"
        ) from ex
    return (
        st.from_type(key_model)
        .map(lambda key_model: key_model.__root__)
        .map(lambda key: Href(key=key, url=referrable_type.key_to_url(key)))
    )


def _hypothesis_setup_hook():
    st.register_type_strategy(Href, _hrefs_strategy)
