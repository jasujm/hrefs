"""Tests for Starlette/FastAPI integration"""

# pylint: disable=broad-exception-caught

import uuid
from urllib.parse import quote_plus as quote

from hypothesis import given, strategies as st, assume, provisional as pst
import pydantic
import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route, Mount, WebSocketRoute
from starlette.testclient import TestClient
from starlette.websockets import WebSocket
from typing_extensions import Annotated

from hrefs import BaseReferrableModel, Href, PrimaryKey
from hrefs.starlette import HrefMiddleware, href_context


class Quest(BaseReferrableModel):
    """Quest

    A plain old model
    """

    id: uuid.UUID

    class Config:
        details_view = "get_quest"


class Hero(BaseReferrableModel):
    """Hero seeking quests

    Model whose key is a hyperlink"""

    self: Annotated[Href["Hero"], PrimaryKey(name="id", type_=uuid.UUID)]

    class Config:
        details_view = "get_hero"


Hero.update_forward_refs()


class JournalEntry(BaseReferrableModel):
    """Entry in a hero's journal

    Model whose key consists of multiple path parameters"""

    hero: Annotated[Href[Hero], PrimaryKey]
    entry: Annotated[int, PrimaryKey]

    class Config:
        details_view = "heroes:get_journal"


class Familiar(BaseReferrableModel):
    """Familiar of a hero

    Model whose key consists of path and query parameters
    """

    hero: Annotated[Href[Hero], PrimaryKey]
    name: Annotated[str, PrimaryKey]

    class Config:
        details_view = "heroes:get_familiar"


def _dummy_endpoint(request):
    del request


def _http_endpoint(request: Request):
    hero = Hero(self=request.query_params["id"])
    return PlainTextResponse(hero.self.url)


async def _websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    with href_context(websocket):
        async for id in websocket.iter_text():
            hero = Hero(self=id)
            await websocket.send_text(hero.self.url)
    await websocket.close()


app = Starlette(
    routes=[
        Route("/quests/{id}", name="get_quest", endpoint=_dummy_endpoint),
        Route("/heroes/{id}", name="get_hero", endpoint=_dummy_endpoint),
        Mount(
            "/heroes/{hero_id}",
            name="heroes",
            routes=[
                Route("/journal/{entry}", name="get_journal", endpoint=_dummy_endpoint),
                Route("/familiar", name="get_familiar", endpoint=_dummy_endpoint),
            ],
        ),
        Route("/http", endpoint=_http_endpoint),
        WebSocketRoute("/ws", endpoint=_websocket_endpoint),
    ],
    middleware=[Middleware(HrefMiddleware)],
)


@pytest.fixture(scope="class")
def appcontext():
    """Provides hyperlink resolution context for Starlette apps"""
    with href_context(app, base_url="http://example.com"):
        yield


@pytest.mark.usefixtures("appcontext")
class TestParsing:
    """Parsing tests"""

    @given(href=st.from_type(Href[Quest]))
    def test_quest_href(self, href):
        assert href.url == f"http://example.com/quests/{href.key}"

    @given(quest_id=st.uuids())
    def test_parse_quest_from_key(self, quest_id):
        href = pydantic.parse_obj_as(Href[Quest], quest_id)
        assert href == Href(key=quest_id, url=f"http://example.com/quests/{quest_id}")

    @given(key=st.one_of(st.text(), st.tuples(st.uuids(), st.text())))
    def test_parse_quest_from_fail(self, key):
        try:
            uuid.UUID(key)
        except Exception:
            with pytest.raises(pydantic.ValidationError):
                pydantic.parse_obj_as(Href[Quest], key)
        else:
            assume(False)

    @given(quest_id=st.uuids())
    def test_parse_quest_from_url(self, quest_id):
        url = f"http://example.com/quests/{quest_id}"
        href = pydantic.parse_obj_as(Href[Quest], url)
        assert href == Href(key=quest_id, url=url)

    @given(
        url=st.one_of(
            pst.urls(),
            st.integers().map(lambda key: f"http://example.com/quests/{key}"),
            st.uuids().map(lambda key: f"http://example.com/quests?key={key}"),
            st.uuids().map(lambda key: f"http://example.com/heroes/{key}"),
        )
    )
    def test_parse_quest_from_url_fail(self, url):
        with pytest.raises(pydantic.ValidationError):
            pydantic.parse_obj_as(Href[Quest], url)

    @given(href=st.from_type(Href[Hero]))
    def test_hero_href(self, href):
        assert href.url == f"http://example.com/heroes/{href.key}"

    @given(hero_id=st.uuids())
    def test_parse_hero_from_key(self, hero_id):
        href = pydantic.parse_obj_as(Href[Hero], hero_id)
        assert href == Href(key=hero_id, url=f"http://example.com/heroes/{hero_id}")

    @given(key=st.one_of(st.text(), st.tuples(st.uuids(), st.text())))
    def test_parse_hero_from_key_fail(self, key):
        try:
            uuid.UUID(key)
        except Exception:
            with pytest.raises(pydantic.ValidationError):
                pydantic.parse_obj_as(Href[Hero], key)
        else:
            assume(False)

    @given(hero_id=st.uuids())
    def test_parse_hero_from_url(self, hero_id):
        url = f"http://example.com/heroes/{hero_id}"
        href = pydantic.parse_obj_as(Href[Hero], url)
        assert href == Href(key=hero_id, url=url)

    @given(
        url=st.one_of(
            pst.urls(),
            st.integers().map(lambda key: f"http://example.com/heroes/{key}"),
            st.uuids().map(lambda key: f"http://example.com/heroes?key={key}"),
            st.uuids().map(lambda key: f"http://example.com/quests/{key}"),
        )
    )
    def test_parse_hero_from_url_fail(self, url):
        with pytest.raises(pydantic.ValidationError):
            pydantic.parse_obj_as(Href[Hero], url)

    @given(href=st.from_type(Href[JournalEntry]))
    def test_journal_href(self, href):
        assert (
            href.url
            == f"http://example.com/heroes/{href.key[0].key}/journal/{href.key[1]}"
        )

    @given(hero_id=st.uuids(), entry=st.integers())
    def test_parse_journal_from_key(self, hero_id, entry):
        hero_url = f"http://example.com/heroes/{hero_id}"
        href = pydantic.parse_obj_as(Href[JournalEntry], (hero_id, entry))
        assert href == Href(
            key=(Href(key=hero_id, url=hero_url), entry),
            url=f"{hero_url}/journal/{entry}",
        )

    @given(key=st.one_of(st.uuids(), st.tuples(st.uuids(), st.text())))
    def test_parse_journal_from_key_fail(self, key):
        try:
            int(key[1])
        except Exception:
            with pytest.raises(pydantic.ValidationError):
                pydantic.parse_obj_as(Href[JournalEntry], key)
        else:
            assume(False)

    @given(hero_id=st.uuids(), entry=st.integers())
    def test_parse_journal_from_url(self, hero_id, entry):
        hero_url = f"http://example.com/heroes/{hero_id}"
        url = f"{hero_url}/journal/{entry}"
        href = pydantic.parse_obj_as(Href[JournalEntry], url)
        assert href == Href(key=(Href(key=hero_id, url=hero_url), entry), url=url)

    @given(
        url=st.one_of(
            pst.urls(),
            st.tuples(st.uuids(), st.uuids()).map(
                lambda key: f"http://example.com/heroes/{key[0]}/journal/{key[1]}"
            ),
            st.tuples(st.integers(), st.integers()).map(
                lambda key: f"http://example.com/heroes/{key[0]}/journal/{key[1]}"
            ),
            st.tuples(st.uuids(), st.integers()).map(
                lambda key: f"http://example.com/heroes/{key[0]}/journal?entry={key[1]}"
            ),
            st.tuples(st.uuids(), st.integers()).map(
                lambda key: f"http://example.com/heroes/{key[0]}/familiar?name={key[1]}"
            ),
        )
    )
    def test_parse_journal_from_url_fail(self, url):
        with pytest.raises(pydantic.ValidationError):
            pydantic.parse_obj_as(Href[JournalEntry], url)

    @given(href=st.from_type(Href[Familiar]))
    def test_familiar_href(self, href):
        assert (
            href.url
            == f"http://example.com/heroes/{href.key[0].key}/familiar?name={quote(href.key[1])}"
        )

    @given(hero_id=st.uuids(), name=st.text())
    def test_parse_familiar_from_key(self, hero_id, name):
        hero_url = f"http://example.com/heroes/{hero_id}"
        href = pydantic.parse_obj_as(Href[Familiar], (hero_id, name))
        assert href == Href(
            key=(Href(key=hero_id, url=hero_url), name),
            url=f"{hero_url}/familiar?name={quote(name)}",
        )

    @given(key=st.one_of(st.uuids(), st.tuples(st.integers(), st.text())))
    def test_parse_familiar_from_key_fail(self, key):
        with pytest.raises(pydantic.ValidationError):
            pydantic.parse_obj_as(Href[Familiar], key)

    @given(hero_id=st.uuids(), name=st.text())
    def test_parse_familiar_from_url(self, hero_id, name):
        hero_url = f"http://example.com/heroes/{hero_id}"
        url = f"{hero_url}/familiar?name={quote(name)}"
        href = pydantic.parse_obj_as(Href[Familiar], url)
        assert href == Href(key=(Href(key=hero_id, url=hero_url), name), url=url)

    @given(
        url=st.one_of(
            pst.urls(),
            st.tuples(st.integers(), st.text()).map(
                lambda key: f"http://example.com/heroes/{key[0]}/familiar?name={quote(key[1])}"
            ),
            st.tuples(st.uuids(), st.text()).map(
                lambda key: f"http://example.com/heroes/{key[0]}/familiar/{quote(key[1])}"
            ),
            st.tuples(st.uuids(), st.integers()).map(
                lambda key: f"http://example.com/heroes/{key[0]}/journal/{key[1]}"
            ),
        )
    )
    def test_parse_familiar_from_url_fail(self, url):
        with pytest.raises(pydantic.ValidationError):
            pydantic.parse_obj_as(Href[Familiar], url)


def test_http_endpoint():
    id = uuid.uuid4()
    client = TestClient(app)
    response = client.get(f"/http?id={id}")
    assert response.text == f"http://testserver/heroes/{id}"


def test_websocket_endpoint():
    id = uuid.uuid4()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_text(id)
        response = websocket.receive_text()
    assert response == f"http://testserver/heroes/{id}"


def test_app_as_href_context_without_base_url_fails():
    with pytest.raises(RuntimeError):
        with href_context(app):
            pydantic.parse_obj_as(Href[Hero], uuid.uuid4())


def test_referrable_model_deprecated() -> None:
    # pylint: disable=import-outside-toplevel
    from hrefs.starlette import ReferrableModel

    with pytest.warns(DeprecationWarning):

        class _MyModel(ReferrableModel):
            id: int
