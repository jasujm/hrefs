"""Hypothesis plugin"""

import typing

import typing_extensions
import hypothesis.strategies as st

from .href import Href
from .model import BaseReferrableModel


def _hrefs_strategy(model_type: typing.Type[Href]):
    args = typing_extensions.get_args(model_type)
    if len(args) != 1:
        raise ValueError("Cannot create strategy for plain Href")
    referrable_type = args[0]
    if not issubclass(referrable_type, BaseReferrableModel):
        raise ValueError(
            f"Cannot create strategy for Href[{referrable_type.__name__}]: "
            f"{referrable_type.__name__} is not subclass of BaseReferrableModel"
        )
    return (
        st.builds(referrable_type._key_model)  # pylint: disable=protected-access
        .map(lambda key_model: key_model.__root__)  # type: ignore
        .map(lambda key: Href(key=key, url=referrable_type.key_to_url(key)))
    )


def _hypothesis_setup_hook():
    st.register_type_strategy(Href, _hrefs_strategy)
