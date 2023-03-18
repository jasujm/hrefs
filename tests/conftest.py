"""Test configurations for the hrefs library"""

import re
import typing

import pytest

from hrefs.model import HrefResolver, resolve_hrefs

_URL_RE = re.compile(r"\Ahttp://example\.com/[a-z_]+/(-?\d+(/-?\d+)*)\Z")


class _MyHrefResolver(HrefResolver):
    def key_to_url(self, key, *, model_cls):
        override = getattr(model_cls, "_key_to_url_override", None)
        if override:
            return override(key)
        if isinstance(key, typing.Iterable):
            key = "/".join(str(key_part) for key_part in key)
        return f"http://example.com/{model_cls.__name__.lower() + 's'}/{key}"

    def url_to_key(self, url, *, model_cls):
        override = getattr(model_cls, "_url_to_key_override", None)
        if override:
            return override(url)
        match = _URL_RE.match(url)
        parts = match.group(1).split("/")
        if len(parts) == 1:
            return int(parts[0])
        return tuple(int(part) for part in parts)


@pytest.fixture(scope="module")
def href_resolver():
    """Provides hyperlink resolver for tests"""

    with resolve_hrefs(_MyHrefResolver()) as resolver:
        yield resolver
