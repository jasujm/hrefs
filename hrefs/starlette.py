"""Starlette integration"""

import functools
import itertools
import typing
import warnings

import pydantic
from starlette.datastructures import URL, QueryParams
from starlette.requests import HTTPConnection
from starlette.applications import Starlette
from starlette.routing import Route, BaseRoute, Mount, Match
from starlette.types import ASGIApp, Scope, Receive, Send

from .model import BaseReferrableModel, HrefResolver, resolve_hrefs, _URL_MODEL
from .errors import ReferrableModelError

RequestOrApp = typing.Union[HTTPConnection, Starlette]
BaseUrl = typing.Union[str, URL]
ModelType = typing.Type[BaseReferrableModel]
RouteChain = typing.List[typing.Union[Route, Mount]]


def _get_details_view(model_cls: ModelType) -> str:
    try:
        return getattr(model_cls.__config__, "details_view")
    except AttributeError as ex:
        raise ReferrableModelError(
            f"Referrable model {model_cls.__name__} missing details_view"
        ) from ex


def _calculate_route_chain(
    routes: typing.Iterable[BaseRoute], name: str
) -> typing.Optional[RouteChain]:
    for route in routes:
        if isinstance(route, Route) and route.name == name:
            return [route]
        if isinstance(route, Mount):
            if not route.name or name.startswith(f"{route.name}:"):
                if route.name:
                    remaining_name = name[(len(route.name) + 1) :]
                else:
                    remaining_name = name
                route_chain = _calculate_route_chain(route.routes, remaining_name)
                if route_chain is not None:
                    route_chain.insert(0, route)
                    return route_chain
    return None


def _get_params_from_route(route: typing.Union[Route, Mount]) -> typing.Set[str]:
    keys = set(route.param_convertors.keys())
    if isinstance(route, Mount):
        keys.remove("path")
    return keys


@functools.lru_cache(maxsize=None)
def _get_route_chain(app: Starlette, model_cls: ModelType) -> RouteChain:
    details_view = _get_details_view(model_cls)
    route_chain = _calculate_route_chain(app.routes, details_view)
    if not route_chain:
        raise ReferrableModelError(
            f"Could not find route {details_view} for model {model_cls.__name__}"
        )
    return route_chain


@functools.lru_cache(maxsize=None)
def _get_path_param_keys(app: Starlette, model_cls: ModelType) -> typing.Set[str]:
    route_chain = _get_route_chain(app, model_cls)
    return set(
        itertools.chain.from_iterable(
            _get_params_from_route(route) for route in route_chain
        )
    )


class _StarletteHrefResolver(HrefResolver):
    def __init__(
        self, request_or_app: RequestOrApp, base_url: typing.Optional[BaseUrl]
    ):
        self.request_or_app = request_or_app
        self.base_url = base_url

    def _get_app(self) -> Starlette:
        if isinstance(self.request_or_app, HTTPConnection):
            return self.request_or_app.app
        return self.request_or_app

    def _get_base_url(self) -> BaseUrl:
        assert not isinstance(self.request_or_app, HTTPConnection)
        if not self.base_url:
            raise RuntimeError(
                "href_context must have base_url set if using application as context"
            )
        return self.base_url

    def key_to_url(
        self, key: typing.Any, *, model_cls: ModelType
    ) -> pydantic.AnyHttpUrl:
        path_param_keys = _get_path_param_keys(self._get_app(), model_cls)
        details_view = _get_details_view(model_cls)
        path_and_query_params = model_cls.key_to_params(key)
        path_params = {
            k: v for (k, v) in path_and_query_params.items() if k in path_param_keys
        }
        if len(path_params) != len(path_param_keys):
            missing_params = path_param_keys - set(path_params.keys())
            raise ReferrableModelError(
                f"Could not resolve {key} into URL. The following parameters are expected "
                f"but missing from the model key: {', '.join(missing_params)}"
            )
        query_params = {
            k: v for (k, v) in path_and_query_params.items() if k not in path_param_keys
        }
        if isinstance(self.request_or_app, HTTPConnection):
            url = self.request_or_app.url_for(details_view, **path_params)
        else:
            url = self.request_or_app.url_path_for(
                details_view, **path_params
            ).make_absolute_url(self._get_base_url())
        # In starlette<0.26 the url conversion methods return string
        # Convert it in case an older version is in use
        if isinstance(url, str):  # pragma: no cover
            url = URL(url)
        return _URL_MODEL.parse_obj(  # type: ignore
            str(url.replace_query_params(**query_params))
        ).__root__

    def url_to_key(
        self, url: pydantic.AnyHttpUrl, *, model_cls: ModelType
    ) -> typing.Any:
        route_chain = _get_route_chain(self._get_app(), model_cls)
        assert len(route_chain) > 0
        path = url.path
        query_params = QueryParams(url.query or "")
        path_params = {}
        *mount_routes, final_route = route_chain
        for route in mount_routes:
            assert isinstance(route, Mount)
            match_type, scope = route.matches(
                {"type": "http", "method": "GET", "path": path}
            )
            if match_type == Match.FULL and scope:
                scope_path_params = scope.get("path_params", {})
                path_params.update(scope_path_params)
                path = scope["path"]
            else:
                break
        else:
            assert isinstance(final_route, Route)
            match_type, scope = final_route.matches(
                {"type": "http", "method": "GET", "path": path}
            )
            if match_type == Match.FULL and scope:
                scope_path_params = scope.get("path_params", {})
                path_params.update(scope_path_params)
                path_and_query_params = {
                    **path_params,
                    **query_params,
                }
                return model_cls.params_to_key(path_and_query_params)
        raise ValueError(f"Invalid URL {url} for {model_cls.__name__}")


def href_context(
    request_or_app: RequestOrApp, *, base_url: typing.Optional[BaseUrl] = None
) -> typing.ContextManager[_StarletteHrefResolver]:
    """Context manager that sets hyperlink context

    Makes ``request_or_app`` responsible for converting between keys and URLs in
    hyperlinks to :class:`BaseReferrableModel`.  The context can be either of
    the following:

    * A :class:`starlette.requests.HTTPConnection` instance -- that is a HTTP
      request or websocket

    * A :class:`starlette.applications.Starlette` instance. Note that
      ``base_url`` needs to be provided when using application to convert the URL
      path to absolute URL.

    :func:`href_context()` is used as a context manager that automatically
    clears the context when exiting.  The contexts stack so you can even use
    nested contexts if you're feeling adventurous.

    .. code-block:: python

        with href_context(request):
            '''Parse and generate hyperlinks, with base URL from the request'''

    If you want to use an application as hyperlink context, you'll need to
    provide base URL manually:

    .. code-block:: python

        with href_context(app, base_url="http://example.com"):
            '''Parse and generate hyperlinks, with base URL from the argument'''

    .. note::

        For normal use where hyperlinks are parsed or generated inside request
        handlers of a Starlette app, it is recommended to use
        :class:`HrefMiddleware` to automatically set the context.

    Arguments:
        request_or_app: The request or app to be used as hyperlink context
        base_url: The base URL (needed when using application as context)
    """
    return resolve_hrefs(_StarletteHrefResolver(request_or_app, base_url))


class HrefMiddleware:
    """Middleware for resolving hyperlinks

    Provide the necessary context for resolving hyperlinks for a Starlette app.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        connection = HTTPConnection(scope)
        with href_context(connection):
            await self.app(scope, receive, send)


class ReferrableModel(BaseReferrableModel):
    """Referrable model with Starlette integration

    .. deprecated::

       Models should inherit :class:`BaseReferrableModel` directly
    """

    def __init_subclass__(cls, *args, **kwargs):
        warnings.warn(
            "Models should inherit BaseReferrableModel directly", DeprecationWarning
        )
