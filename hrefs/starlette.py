"""Starlette integration"""

import contextvars

import pydantic
import starlette.requests
import starlette.middleware.base

from .model import ReferrableModel


_request_var: contextvars.ContextVar[
    starlette.requests.Request
] = contextvars.ContextVar("_request_var")


class HrefMiddleware(starlette.middleware.base.BaseHTTPMiddleware):
    """Middleware for resolving hrefs

    This middleware needs to be added to the middleware stack of the Starlette
    app using the :class:`ReferrableStarletteModel`.
    """

    @staticmethod
    async def dispatch(request: starlette.requests.Request, call_next):
        _request_var.set(request)
        return await call_next(request)


class ReferrableStarletteModel(ReferrableModel):
    """Referrable model with Starlette integration

    This class implements the :class:`hrefs.ReferrableModel` with the following
    features:

    * Its key type is inferred from the ``id`` field of the subclass

    * Its URL type is always :class:`pydantic.AnyHttpUrl`

    * When converting between key and URL, it relies on the Starlette request
      objects. Thus a :class:`ReferrableStarletteModel` is only usable within
      request handlers or middleware above the :class:`HrefMiddleware` in the
      middleware stack of the application.

    Here is a minimal example of a model having key type ``int`` (inferred from
    the ``id`` property), and using route called ``"my_view"`` to convert
    to/from URLs.

    .. code-block:: python

        class MyModel(ReferrableStarletteModel):
            id: int

            class Config:
                default_view = "my_view"

    For a more complete example of using :mod:`hrefs` library with Starlette,
    please refer to :ref:`quickstart`.

    """

    @classmethod
    def href_types(cls):
        return cls._get_key_type(), pydantic.AnyHttpUrl

    @classmethod
    def key_to_url(cls, key):
        request = _request_var.get()
        default_view = cls._get_default_view()
        return pydantic.parse_obj_as(
            pydantic.AnyHttpUrl, request.url_for(default_view, id=key)
        )

    @classmethod
    def url_to_key(cls, url: pydantic.AnyHttpUrl):
        request = _request_var.get()
        default_view = cls._get_default_view()
        for route in request.app.routes:
            if route.name == default_view:
                _, scope = route.matches(
                    {"type": "http", "method": "GET", "path": url.path}
                )
                if scope:
                    return pydantic.parse_obj_as(
                        cls._get_key_type(), scope["path_params"]["id"]
                    )
        raise ValueError(f"Could not resolve {url} into key")

    @classmethod
    def _get_key_type(cls):
        return cls.__fields__["id"].type_

    @classmethod
    def _get_default_view(cls):
        return getattr(cls.__config__, "default_view")
