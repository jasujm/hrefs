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

from hrefs import Href, PrimaryKey
from hrefs.starlette import ReferrableModel, HrefMiddleware, href_context


class Comment(ReferrableModel):
    id: uuid.UUID

    class Config:
        details_view = "get_comment"


class Article(ReferrableModel):
    self: Annotated[Href["Article"], PrimaryKey(type_=uuid.UUID, name="id")]
    comments: typing.List[Href[Comment]]
    current_revision: Href["ArticleRevision"]

    class Config:
        details_view = "get_article"


class ArticleRevision(ReferrableModel):
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
save_article_var: contextvars.ContextVar[
    typing.Callable[[Article], None]
] = contextvars.ContextVar("save_article_var")


app = fastapi.FastAPI(middleware=[fastapi.middleware.Middleware(HrefMiddleware)])


@pytest.fixture
def appcontext():
    with href_context(app, base_url="http://testserver"):
        yield


@app.get("/articles/{id}", response_model=Article)
async def get_article(id: uuid.UUID):
    assert id == article_var.get()
    return Article(
        self=id,
        comments=comments_var.get(),
        current_revision=(id, revision_var.get()),
    )


@app.post("/articles")
async def post_article(article: Article):
    save_article = save_article_var.get()
    save_article(article)


@app.get("/comments/{id}", response_model=Comment)
async def get_comment(id: uuid.UUID):
    assert id in comments_var.get()
    return Comment(id=id)


@app.get("/articles/{article_id}/revisions/{revision}")
async def get_revision(article_id: uuid.UUID, revision: int):
    assert article_id == article_var.get()
    return ArticleRevision(article=article_id, revision=revision)


@app.websocket("/comment")
async def echo_comments(websocket: fastapi.WebSocket):
    await websocket.accept()
    comment_id = await websocket.receive_json()
    with href_context(websocket):
        comment = pydantic.parse_obj_as(Href[Comment], comment_id)
    await websocket.send_json(comment.url)
    await websocket.close()


client = fastapi.testclient.TestClient(app)


@given(st.uuids(), st.integers(), st.lists(st.uuids(), min_size=1))
def test_parse_key_to_href(article_id, revision, comment_ids):
    article_var.set(article_id)
    revision_var.set(revision)
    comments_var.set(comment_ids)
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


@given(st.uuids(), st.integers(), st.lists(st.uuids(), min_size=1))
def test_parse_url_to_href(article_id, revision, comment_ids):
    def assert_article(article: Article):
        assert article.self.key == article_id
        assert [comment_href.key for comment_href in article.comments] == comment_ids
        _article, _revision = article.current_revision.key
        assert _article.key == article_id
        assert _revision == revision

    save_article_var.set(assert_article)
    response = client.post(
        "/articles",
        data=json.dumps(
            dict(
                self=str(article_id),
                comments=[f"http://testserver/comments/{id}" for id in comment_ids],
                current_revision=f"http://testserver/articles/{article_id}/revisions/{revision}",
            )
        ),
    )
    assert response.status_code == fastapi.status.HTTP_200_OK, response.text


@given(st.uuids(), st.lists(st.uuids(), min_size=1))
def test_parse_invalid_url_fails(article_id, comment_ids):
    response = client.post(
        "/articles",
        data=json.dumps(
            dict(
                self=str(article_id),
                comments=[
                    f"http://testserver/not/a/real/route/{id}" for id in comment_ids
                ],
            )
        ),
    )
    assert response.status_code == fastapi.status.HTTP_422_UNPROCESSABLE_ENTITY


@given(st.uuids())
@settings(deadline=1000)
def test_websocket_as_href_context(comment_id):
    with client.websocket_connect("/comment") as websocket:
        websocket.send_json(str(comment_id))
        response = websocket.receive_json()
    assert response == f"http://testserver/comments/{comment_id}"


@given(comment_id=st.uuids())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_app_as_href_context_parse_key(appcontext, comment_id):
    comment = pydantic.parse_obj_as(Href[Comment], comment_id)
    assert comment == Href(
        key=comment_id, url=f"http://testserver/comments/{comment_id}"
    )


@given(comment_id=st.uuids())
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_app_as_href_context_parse_url(appcontext, comment_id):
    comment_url = f"http://testserver/comments/{comment_id}"
    comment = pydantic.parse_obj_as(Href[Comment], comment_url)
    assert comment == Href(key=comment_id, url=comment_url)


@given(st.uuids())
def test_app_as_href_context_without_base_url_fails(comment_id):
    with pytest.raises(RuntimeError):
        with href_context(app):
            pydantic.parse_obj_as(Href[Comment], comment_id)
