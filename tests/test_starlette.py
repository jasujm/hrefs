"""Tests for Starlette/FastAPI integration"""

import contextvars
import json
import random
import typing
import uuid

import fastapi
import fastapi.middleware
import fastapi.testclient
from hypothesis import given, strategies as st, settings, HealthCheck
import pydantic
import pytest
from typing_extensions import Annotated

from hrefs import BaseReferrableModel, Href, PrimaryKey
from hrefs.starlette import HrefMiddleware, href_context


class Comment(BaseReferrableModel):
    """Comment"""

    id: uuid.UUID

    class Config:
        details_view = "get_comment"


class Author(BaseReferrableModel):
    """Article author"""

    id: uuid.UUID

    class Config:
        details_view = "authors:get_author"


class Article(BaseReferrableModel):
    """Article"""

    self: Annotated[Href["Article"], PrimaryKey(type_=uuid.UUID, name="id")]
    comments: typing.List[Href[Comment]]
    current_revision: Href["ArticleRevision"]
    author: Href[Author]

    class Config:
        details_view = "get_article"


class ArticleRevision(BaseReferrableModel):
    """Article revision"""

    article: Annotated[Href[Article], PrimaryKey]
    revision: Annotated[int, PrimaryKey]

    class Config:
        details_view = "get_revision"


Article.update_forward_refs()


article_var: contextvars.ContextVar[uuid.UUID] = contextvars.ContextVar("article_var")
revision_var: contextvars.ContextVar[int] = contextvars.ContextVar("revision_var")
comments_var: contextvars.ContextVar[typing.List[uuid.UUID]] = contextvars.ContextVar(
    "comments_var"
)
author_var: contextvars.ContextVar[uuid.UUID] = contextvars.ContextVar("author_var")
save_article_var: contextvars.ContextVar[
    typing.Callable[[Article], None]
] = contextvars.ContextVar("save_article_var")


app = fastapi.FastAPI(middleware=[fastapi.middleware.Middleware(HrefMiddleware)])


@pytest.fixture
def appcontext():
    """Provides hyperlink resolution context for Starlette apps"""
    with href_context(app, base_url="http://testserver"):
        yield


@app.get("/articles/{id}", response_model=Article)
async def get_article(id: uuid.UUID):
    """Get article"""

    assert id == article_var.get()
    return Article(
        self=id,
        comments=comments_var.get(),
        current_revision=(id, revision_var.get()),
        author=author_var.get(),
    )


@app.post("/articles")
async def post_article(article: Article):
    """Post article"""

    save_article = save_article_var.get()
    save_article(article)


@app.get("/comments", response_model=Comment)
async def get_comment(id: uuid.UUID):
    """Get comment"""

    assert id in comments_var.get()
    return Comment(id=id)


@app.get("/articles/{article_id}/revisions/{revision}")
async def get_revision(article_id: uuid.UUID, revision: int):
    """Get revision"""

    assert article_id == article_var.get()
    return ArticleRevision(article=article_id, revision=revision)


@app.websocket("/comment")
async def echo_comments(websocket: fastapi.WebSocket):
    """Echo comment (a websocket endpoint)"""

    await websocket.accept()
    comment_id = await websocket.receive_json()
    with href_context(websocket):
        comment = pydantic.parse_obj_as(Href[Comment], comment_id)
    await websocket.send_json(comment.url)
    await websocket.close()


author_app = fastapi.FastAPI()


@author_app.get("/{id}")
def get_author(id: uuid.UUID):
    """Get author"""

    assert id == author_var.get()
    return Author(id=id)


app.mount("/authors", author_app, name="authors")

client = fastapi.testclient.TestClient(app)


@given(
    article_id=st.uuids(),
    revision=st.integers(),
    comment_ids=st.lists(st.uuids(), min_size=1),
    author_id=st.uuids(),
)
def test_parse_key_to_href(article_id, revision, comment_ids, author_id):
    article_var.set(article_id)
    revision_var.set(revision)
    comments_var.set(comment_ids)
    author_var.set(author_id)
    response = client.get(f"/articles/{article_id}")
    assert response.status_code == fastapi.status.HTTP_200_OK, response.text
    article = response.json()
    comment_href, comment_id = random.choice(
        list(zip(article["comments"], comment_ids))
    )
    comment = client.get(comment_href).json()
    assert uuid.UUID(comment["id"]) == comment_id
    current_revision_href = article["current_revision"]
    current_revision = client.get(current_revision_href).json()
    assert current_revision == {
        "article": f"http://testserver/articles/{article_id}",
        "revision": revision,
    }
    author_href = article["author"]
    author = client.get(author_href).json()
    assert author == {"id": str(author_id)}


@given(
    article_id=st.uuids(),
    revision=st.integers(),
    comment_ids=st.lists(st.uuids(), min_size=1),
    author_id=st.uuids(),
)
def test_parse_url_to_href(article_id, revision, comment_ids, author_id):
    def assert_article(article: Article):
        assert article.self.key == article_id
        assert [comment_href.key for comment_href in article.comments] == comment_ids
        _article, _revision = article.current_revision.key
        assert _article.key == article_id
        assert _revision == revision
        assert article.author.key == author_id

    save_article_var.set(assert_article)
    response = client.post(
        "/articles",
        content=json.dumps(
            {
                "self": str(article_id),
                "comments": [
                    f"http://testserver/comments?id={id}" for id in comment_ids
                ],
                "current_revision": f"http://testserver/articles/{article_id}/revisions/{revision}",
                "author": f"http://testserver/authors/{author_id}",
            }
        ),
    )
    assert response.status_code == fastapi.status.HTTP_200_OK, response.text


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    url=st.one_of(
        st.just("http://testserver/not/a/real/route"),
        st.just("http://testserver/comments?wrong=query"),
        st.integers().map(lambda n: f"http://testserver/comments?id={n}"),
        st.uuids().map(lambda id: f"http://testserver/articles/{id}"),
    )
)
def test_parse_invalid_url_fails_comments(url, appcontext):
    del appcontext
    with pytest.raises(pydantic.ValidationError):
        pydantic.parse_obj_as(Href[Comment], url)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    key=st.one_of(
        st.booleans(),
        st.integers(),
        st.tuples(st.booleans(), st.integers()),
    )
)
def test_parse_invalid_key_fails_comments(key, appcontext):
    del appcontext
    with pytest.raises(pydantic.ValidationError):
        pydantic.parse_obj_as(Href[Comment], key)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    url=st.one_of(
        st.just("http://testserver/not/a/real/route"),
        st.integers().map(lambda n: f"http://testserver/authors/{n}"),
        st.uuids().map(lambda id: f"http://testserver/comments?id={id}"),
    )
)
def test_parse_invalid_url_fails_authors(url, appcontext):
    del appcontext
    with pytest.raises(pydantic.ValidationError):
        pydantic.parse_obj_as(Href[Author], url)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    key=st.one_of(
        st.booleans(),
        st.integers(),
        st.tuples(st.booleans(), st.integers()),
    )
)
def test_parse_invalid_key_fails_authors(key, appcontext):
    del appcontext
    with pytest.raises(pydantic.ValidationError):
        pydantic.parse_obj_as(Href[Author], key)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    url=st.one_of(
        st.just("http://testserver/not/a/real/route"),
        st.integers().map(lambda n: f"http://testserver/articles/{n}"),
        st.uuids().map(lambda id: f"http://testserver/comments?id={id}"),
    )
)
def test_parse_invalid_url_fails_articles(url, appcontext):
    del appcontext
    with pytest.raises(pydantic.ValidationError):
        pydantic.parse_obj_as(Href[Article], url)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    key=st.one_of(
        st.booleans(),
        st.integers(),
        st.tuples(st.booleans(), st.integers()),
    )
)
def test_parse_invalid_key_fails_articles(key, appcontext):
    del appcontext
    with pytest.raises(pydantic.ValidationError):
        pydantic.parse_obj_as(Href[Article], key)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    url=st.one_of(
        st.just("http://testserver/not/a/real/route"),
        st.tuples(st.uuids(), st.uuids()).map(
            lambda key: f"http://testserver/articles/{key[0]}/revisions/{key[1]}"
        ),
        st.tuples(st.integers(), st.integers()).map(
            lambda key: f"http://testserver/articles/{key[0]}/revisions/{key[1]}"
        ),
        st.tuples(st.uuids(), st.integers()).map(
            lambda key: f"http://testserver/articles/{key[0]}?revision={key[1]}"
        ),
    )
)
def test_parse_invalid_url_fails_revisions(url, appcontext):
    del appcontext
    with pytest.raises(pydantic.ValidationError):
        pydantic.parse_obj_as(Href[ArticleRevision], url)


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    key=st.one_of(
        st.booleans(),
        st.integers(),
        st.tuples(st.booleans(), st.integers()),
    )
)
def test_parse_invalid_key_fails_revisions(key, appcontext):
    del appcontext
    with pytest.raises(pydantic.ValidationError):
        pydantic.parse_obj_as(Href[ArticleRevision], key)


def test_websocket_as_href_context():
    comment_id = uuid.uuid4()
    with client.websocket_connect("/comment") as websocket:
        websocket.send_json(str(comment_id))
        response = websocket.receive_json()
    assert response == f"http://testserver/comments?id={comment_id}"


def test_app_as_href_context_parse_key(appcontext):
    del appcontext
    comment_id = uuid.uuid4()
    comment = pydantic.parse_obj_as(Href[Comment], comment_id)
    assert comment == Href(
        key=comment_id, url=f"http://testserver/comments?id={comment_id}"
    )


def test_app_as_href_context_parse_url(appcontext):
    del appcontext
    comment_id = uuid.uuid4()
    comment_url = f"http://testserver/comments?id={comment_id}"
    comment = pydantic.parse_obj_as(Href[Comment], comment_url)
    assert comment == Href(key=comment_id, url=comment_url)


def test_app_as_href_context_without_base_url_fails():
    comment_id = uuid.uuid4()
    with pytest.raises(RuntimeError):
        with href_context(app):
            pydantic.parse_obj_as(Href[Comment], comment_id)


def test_referrable_model_deprecated() -> None:
    # pylint: disable=import-outside-toplevel
    from hrefs.starlette import ReferrableModel

    with pytest.warns(DeprecationWarning):

        class _MyModel(ReferrableModel):
            id: int
