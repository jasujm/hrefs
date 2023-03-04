"""Starlette integration"""

import typing
import warnings

import pydantic
from starlette.datastructures import URL, QueryParams
from starlette.requests import HTTPConnection, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.applications import Starlette
from starlette.routing import Route, BaseRoute, Mount, Match

from .model import BaseReferrableModel, HrefResolver, resolve_hrefs, _URL_MODEL

RequestOrApp = typing.Union[HTTPConnection, Starlette]
BaseUrl = typing.Union[str, URL]
ModelType = typing.Type[BaseReferrableModel]
AppAndModelType = typing.Tuple[Starlette, ModelType]


def _get_path_param_keys(
    routes: typing.Iterable[BaseRoute], name: str
) -> typing.Optional[typing.Set[str]]:
    for route in routes:
        if isinstance(route, Route) and route.name == name:
            return set(route.param_convertors.keys())
        if isinstance(route, Mount):
            if not route.name or name.startswith(f"{route.name}:"):
                if route.name:
                    name = name[(len(route.name) + 1) :]
                path_param_keys = _get_path_param_keys(route.routes, name)
                if path_param_keys is not None:
                    path_param_keys.update(
                        key for key in route.param_convertors.keys() if key != "path"
                    )
                return path_param_keys
    return None


class _StarletteHrefResolver(HrefResolver):
    _path_param_keys_cache: typing.Dict[AppAndModelType, typing.Set[str]] = {}

    def __init__(
        self, request_or_app: RequestOrApp, base_url: typing.Optional[BaseUrl]
    ):
        self.request_or_app = request_or_app
        self.base_url = base_url

    def _get_app(self) -> Starlette:
        if isinstance(self.request_or_app, HTTPConnection):
            return self.request_or_app.app
        return self.request_or_app

    def _get_routes(self) -> typing.Sequence[BaseRoute]:
        if isinstance(self.request_or_app, HTTPConnection):
            app = self.request_or_app.app
        else:
            app = self.request_or_app
        return app.routes

    def _get_base_url(self) -> BaseUrl:
        if isinstance(self.request_or_app, HTTPConnection):
            return self.request_or_app.base_url
        if not self.base_url:
            raise RuntimeError(
                "href_context must have base_url set if using application as context"
            )
        return self.base_url

    @staticmethod
    def _get_details_view(model_cls: ModelType):
        return getattr(model_cls.__config__, "details_view")

    def key_to_url(
        self, key: typing.Any, *, model_cls: ModelType
    ) -> pydantic.AnyHttpUrl:
        details_view = self._get_details_view(model_cls)

        cache_key = self._get_app(), model_cls
        path_param_keys = self._path_param_keys_cache.get(cache_key)
        if path_param_keys is None:
            routes = self._get_routes()
            path_param_keys = _get_path_param_keys(routes, details_view)
            if path_param_keys is not None:
                self._path_param_keys_cache[cache_key] = path_param_keys

        if path_param_keys is not None:
            path_and_query_params = model_cls.key_to_params(key)
            path_params = {
                k: v for (k, v) in path_and_query_params.items() if k in path_param_keys
            }
            if len(path_params) != len(path_param_keys):
                missing_params = path_param_keys - set(path_params.keys())
                raise ValueError(
                    f"Could not resolve {key} into url. The following path parameters are expected "
                    f"in the route but missing from the model key: {', '.join(missing_params)}"
                )
            query_params = {
                k: v
                for (k, v) in path_and_query_params.items()
                if k not in path_param_keys
            }
            if isinstance(self.request_or_app, HTTPConnection):
                url = self.request_or_app.url_for(details_view, **path_params)
            else:
                url = self.request_or_app.url_path_for(
                    details_view, **path_params
                ).make_absolute_url(self._get_base_url())
            return _URL_MODEL.parse_obj(  # type: ignore
                str(URL(url).replace_query_params(**query_params))
            ).__root__
        raise ValueError(f"Could not resolve {key} into url")

    def url_to_key(
        self, url: pydantic.AnyHttpUrl, *, model_cls: ModelType
    ) -> typing.Any:
        routes = self._get_routes()
        path = url.path
        query_params = QueryParams(url.query or "")
        path_params = {}
        while True:
            for route in routes:
                match_type, scope = route.matches(
                    {"type": "http", "method": "GET", "path": path}
                )
                if match_type == Match.FULL and scope:
                    scope_path_params = scope.get("path_params", {})
                    path_params.update(scope_path_params)
                    if isinstance(route, Mount):
                        routes = route.routes
                        path = scope["path"]
                        break
                    path_and_query_params = {
                        **path_params,
                        **query_params,
                    }
                    return model_cls.params_to_key(path_and_query_params)
            else:
                raise ValueError(f"Could not resolve {url} into key")


def href_context(
    request_or_app: RequestOrApp, *, base_url: typing.Optional[BaseUrl] = None
) -> typing.ContextManager[_StarletteHrefResolver]:
    """Context manager that sets hyperlink context

    Makes ``request_or_app`` responsible for converting between keys and URLs in
    hyperlinks to :class:`BaseReferrableModel`. The context can be either of the
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
       from hrefs import BaseReferrableModel
       from hrefs.starlette import href_context

       app = FastAPI(...)

       class Book(BaseReferrableModel):
           id: int

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
    return resolve_hrefs(_StarletteHrefResolver(request_or_app, base_url))


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

    .. deprecated::

       Models should inherit :class:`BaseReferrableModel` directly
    """

    def __init_subclass__(cls, *args, **kwargs):
        warnings.warn(
            "Models should inherit BaseReferrableModel directly", DeprecationWarning
        )
