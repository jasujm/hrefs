"""Testing utilities"""

import typing

import pydantic

from hrefs import Referrable, Href
from hrefs._util import is_pydantic_2

if is_pydantic_2():

    def parse_obj(type_: typing.Type[typing.Any], value: typing.Any):
        """Parse ``value`` as ``type_``"""
        adapter = pydantic.TypeAdapter(type_)
        return adapter.validate_python(value)

else:

    def parse_obj(type_: typing.Type[typing.Any], value: typing.Any):
        """Parse ``value`` as ``type_``"""
        return pydantic.parse_obj_as(type_, value)


def parse_href(referrable_type: typing.Type[Referrable], value: typing.Any):
    """Parse ``value`` as hyperlink to ``referrable_type``"""
    href_type = Href[referrable_type]  # type: ignore
    return parse_obj(href_type, value)
