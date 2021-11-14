"""Test utilities"""

import typing

from pydantic_href import Href, Referrable

from hypothesis import strategies as st


def hrefs(target: typing.Type[Referrable], key_strategy):
    key_type, _ = target.href_types()
    return key_strategy.map(
        lambda key: Href(key=key, url=target.key_to_url(key), target=target)
    )
