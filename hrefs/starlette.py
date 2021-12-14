"""Starlette integration"""

import contextvars

import pydantic
import starlette.requests
import starlette.middleware.base

from .model import BaseReferrableModel


_request_var: contextvars.ContextVar[
    starlette.requests.Request
] = contextvars.ContextVar("_request_var")


class HrefMiddleware(starlette.middleware.base.BaseHTTPMiddleware):
    """Middleware for resolving hrefs

    This middleware needs to be added to the middleware stack of the Starlette
    app using the :class:`ReferrableModel`.
    """

    @staticmethod
    async def dispatch(request: starlette.requests.Request, call_next):
        _request_var.set(request)
        return await call_next(request)


# pylint: disable=abstract-method
class ReferrableModel(BaseReferrableModel):
    """Referrable model with Starlette integration

    This class implements the :class:`hrefs.BaseReferrableModel` with the
    following features:

    * Its key type is inferred from type annotations as in the base class

    * Its URL type is always :class:`pydantic.AnyHttpUrl`

    * When converting between key and URL, it relies on the Starlette request
      objects. Thus a :class:`ReferrableModel` is only usable within request
      handlers or middleware above the :class:`HrefMiddleware` in the middleware
      stack of the application.

    Here is a minimal example using route called ``"my_view"`` to convert
    to/from URLs:

    .. code-block:: python

        class MyModel(ReferrableModel):
            id: int

            class Config:
                details_view = "my_view"

    For a more complete example of using :mod:`hrefs` library with Starlette,
    please refer to :ref:`quickstart`.
    """

    @staticmethod
    def get_url_type():
        return pydantic.AnyHttpUrl

    @classmethod
    def key_to_url(cls, key):
        request = _request_var.get()
        details_view = cls._get_details_view()
        key_names = cls._key_names
        if len(key_names) > 1:
            kwargs = dict(zip(key_names, key))
        else:
            kwargs = {key_names[0]: key}
        return pydantic.parse_obj_as(
            pydantic.AnyHttpUrl, request.url_for(details_view, **kwargs)
        )

    @classmethod
    def url_to_key(cls, url: pydantic.AnyHttpUrl):
        request = _request_var.get()
        details_view = cls._get_details_view()
        key_names = cls._key_names
        for route in request.app.routes:
            if route.name == details_view:
                _, scope = route.matches(
                    {"type": "http", "method": "GET", "path": url.path}
                )
                if scope:
                    if len(key_names) > 1:
                        path_params = scope["path_params"]
                        key = [path_params[name] for name in key_names]
                    else:
                        key_name = key_names[0]
                        key = scope["path_params"][key_name]
                    return pydantic.parse_obj_as(cls.get_key_type(), key)
        raise ValueError(f"Could not resolve {url} into key")

    @classmethod
    def _get_details_view(cls):
        return getattr(cls.__config__, "details_view")
