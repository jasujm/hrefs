"""Starlette integration"""

import contextlib
import contextvars
import typing

import pydantic
from starlette.datastructures import URL, QueryParams
from starlette.requests import HTTPConnection, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.applications import Starlette
from starlette.routing import Route

from .model import BaseReferrableModel


_URL_MODEL: typing.Type[pydantic.BaseModel] = pydantic.create_model(
    "_URL_MODEL", __root__=(pydantic.AnyHttpUrl, ...)
)

RequestOrApp = typing.Union[HTTPConnection, Starlette]
BaseUrl = typing.Union[str, URL]


_href_context_var: contextvars.ContextVar[
    typing.Tuple[RequestOrApp, typing.Optional[BaseUrl]]
] = contextvars.ContextVar("_href_context_var")

_route_cache: typing.Dict[typing.Tuple[Starlette, str], Route] = {}


def _get_route(route_name: str) -> typing.Optional[Route]:
    request_or_app, _ = _href_context_var.get()
    if isinstance(request_or_app, HTTPConnection):
        app = request_or_app.app
    else:
        app = request_or_app
    cached_route = _route_cache.get((app, route_name))
    if cached_route:
        return cached_route
    for route in app.routes:
        if isinstance(route, Route) and route.name == route_name:
            _route_cache[(app, route_name)] = route
            return route
    return None


def _get_base_url() -> BaseUrl:
    request_or_app, base_url = _href_context_var.get()
    if isinstance(request_or_app, HTTPConnection):
        return request_or_app.base_url
    if not base_url:
        raise RuntimeError(
            "href_context must have base_url set if using application as context"
        )
    return base_url


@contextlib.contextmanager
def href_context(
    request_or_app: RequestOrApp, *, base_url: typing.Optional[BaseUrl] = None
):
    """Context manager that sets hyperlink context

    Makes ``request_or_app`` responsible for converting between keys and URLs in
    hyperlinks to :class:`ReferrableModel`. The context can be either of the
    following:

    * A Starlette ``HTTPConnection`` -- that is HTTP request or websocket

    * A Starlette application. Note that ``base_url`` needs to be provided when
      using application to convert the URL path to absolute URL.

    :func:`href_context()` is used as a context manager that automatically
    clears the context when exiting. The contexts stack so you can even use
    nested contexts if you're feeling adventurous.

    This is an example how to make a websocket handler work with hyperlinks in
    FastAPI:

    .. code-block:: python

       from fastapi import FastAPI, WebSocket
       from hrefs.starlette import ReferrableModel, href_context

       app = FastAPI(...)

       class Book(ReferrableModel):
           id: int

           # ...et cetera...

       @app.websocket("/")
       async def my_awesome_websocket_endpoint(websocket: WebSocket):
           await websocket.accept()
           with href_context(websocket):
               # here you can create and parse Href[Book] instances
               # the base URL will be inferred from the connection

    If you want to use an application as hyperlink context, you'll need to
    provide base URL manually:

    .. code-block:: python

       with href_context(app, base_url="http://example.com"):
           # here you can create and parse Href[Book] instances
           # URLs will be like: http://example.com/book/api/books/1

    .. note::

       For normal use where hyperlinks are parsed or generated inside request
       handlers of a Starlette/FastAPI app, it is recommended to use
       :class:`HrefMiddleware` to automatically set the context.

    Arguments:
        request_or_app: The request or app to be used as hyperlink context
        base_url: The base URL (needed when using application as context)
    """
    token = _href_context_var.set((request_or_app, base_url))
    try:
        yield
    finally:
        _href_context_var.reset(token)


class HrefMiddleware(BaseHTTPMiddleware):
    """Middleware for resolving hyperlinks

    This middleware needs to be added to the middleware stack of a Starlette app
    intending to use this library.
    """

    async def dispatch(self, request: Request, call_next):
        with href_context(request):
            return await call_next(request)


class ReferrableModel(BaseReferrableModel):
    """Referrable model with Starlette integration

    This class is the preferable base class of models in a Starlette/FastAPI
    application. More specifically, it extends the
    :class:`hrefs.BaseReferrableModel` class with the following features:

    * Its key type is inferred from type annotations as in the base class

    * Its URL type is always :class:`pydantic.AnyHttpUrl`

    * It uses a context (app or request) to automatically generate and resolve
      URLs based on routes defined in the application.

    The preferable way to provide :class:`ReferrableModel` its context is by
    adding :class:`HrefMiddleware` to the middleware stack of the application.
    :func:`href_context()` can alternatively be used when using the middleware
    is not possible (for example in websocket handlers or when using hyperlinks
    outside of request handlers).

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

    @classmethod
    def parse_as_url(cls, value: typing.Any) -> typing.Optional[pydantic.AnyHttpUrl]:
        """Parse ``value`` as ``pydantic.AnyHttpUrl``"""
        return cls.try_parse_as(_URL_MODEL, value)

    @classmethod
    def key_to_url(cls, key) -> pydantic.AnyHttpUrl:
        details_view = cls._get_details_view()
        route = _get_route(details_view)
        if route:
            path_and_query_params = cls.key_to_params(key)
            path_param_keys = set(route.param_convertors.keys())
            path_params = {
                k: v for (k, v) in path_and_query_params.items() if k in path_param_keys
            }
            if len(path_params) != len(path_param_keys):
                missing_params = path_param_keys - set(path_params.keys())
                raise ValueError(
                    f"Could not resolve {key} into url. The following path parameters are expected in the route but missing from the model key: {', '.join(missing_params)}"
                )
            query_params = {
                k: v
                for (k, v) in path_and_query_params.items()
                if k not in path_param_keys
            }
            url = URL(
                route.url_path_for(details_view, **path_params).make_absolute_url(
                    _get_base_url()
                )
            ).replace_query_params(**query_params)
            return _URL_MODEL.parse_obj(str(url)).__root__  # type: ignore
        raise ValueError(f"Could not resolve {key} into url")

    @classmethod
    def url_to_key(cls, url: pydantic.AnyHttpUrl) -> typing.Any:
        details_view = cls._get_details_view()
        route = _get_route(details_view)
        if route:
            _, scope = route.matches(
                {"type": "http", "method": "GET", "path": url.path}
            )
            if scope:
                query_params = QueryParams(url.query or "")
                path_and_query_params = {
                    **scope["path_params"],
                    **query_params,
                }
                return cls.params_to_key(path_and_query_params)
        raise ValueError(f"Could not resolve {url} into key")

    @classmethod
    def _get_details_view(cls):
        return getattr(cls.__config__, "details_view")
