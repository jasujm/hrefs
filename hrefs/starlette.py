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
    """Middleware

    An instance of this middleware needs to be added to an Starlette app that
    uses models with `Href` fields.
    """

    @staticmethod
    async def dispatch(request: starlette.requests.Request, call_next):
        _request_var.set(request)
        return await call_next(request)


class ReferrableStarletteModel(ReferrableModel):
    """Referrable model with Starlette integration

    The model assumes there is a route acting as the view for this model
    type. The key of the model instance is encoded as the `id` path parameter of
    the route. The view is specified as using the model `Config` class.

        class MyModel(ReferrableStarletteModel):
            id: int

            class Config:
                default_view = "my_view"
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
