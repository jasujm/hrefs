import contextvars
import json
import random
import typing
import uuid

import fastapi
import fastapi.middleware
import fastapi.testclient
from hypothesis import given, strategies as st
import pydantic

from hrefs import Href, BaseModel
from hrefs.starlette import ReferrableStarletteModel, HrefMiddleware


class Comment(ReferrableStarletteModel):
    id: uuid.UUID

    class Config:
        default_view = "get_comment"


class Article(BaseModel):
    id: uuid.UUID
    comments: typing.List[Href[Comment]]


article_var: contextvars.ContextVar[uuid.UUID] = contextvars.ContextVar("article_var")
comments_var: contextvars.ContextVar[typing.List[uuid.UUID]] = contextvars.ContextVar(
    "comments_var"
)
save_article_var: contextvars.ContextVar[
    typing.Callable[[Article], None]
] = contextvars.ContextVar("save_article_var")


app = fastapi.FastAPI(middleware=[fastapi.middleware.Middleware(HrefMiddleware)])


@app.get("/articles/{id}", response_model=Article)
async def get_article(id: uuid.UUID):
    assert id == article_var.get()
    return Article(
        id=id,
        comments=comments_var.get(),
    )


@app.post("/articles")
async def put_article(article: Article):
    save_article = save_article_var.get()
    save_article(article)


@app.get("/comments/{id}", response_model=Comment)
async def get_comment(id: uuid.UUID):
    assert id in comments_var.get()
    return Comment(id=id)


client = fastapi.testclient.TestClient(app)


@given(st.uuids(), st.lists(st.uuids(), min_size=1))
def test_parse_key_to_href(article_id, comment_ids):
    article_var.set(article_id)
    comments_var.set(comment_ids)
    response = client.get(f"/articles/{article_id}")
    assert response.status_code == fastapi.status.HTTP_200_OK, response.text
    article = response.json()
    comment_href, comment_id = random.choice(
        list(zip(article["comments"], comment_ids))
    )
    comment = client.get(comment_href).json()
    assert uuid.UUID(comment["id"]) == comment_id


@given(st.uuids(), st.lists(st.uuids(), min_size=1))
def test_parse_url_to_href(article_id, comment_ids):
    def assert_article(article: Article):
        assert article.id == article_id
        assert [
            comment_href.get_key() for comment_href in article.comments
        ] == comment_ids

    save_article_var.set(assert_article)
    response = client.post(
        "/articles",
        data=json.dumps(
            dict(
                id=str(article_id),
                comments=[f"http://testclient/comments/{id}" for id in comment_ids],
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
                id=str(article_id),
                comments=[
                    f"http://testclient/not/a/real/route/{id}" for id in comment_ids
                ],
            )
        ),
    )
    assert response.status_code == fastapi.status.HTTP_422_UNPROCESSABLE_ENTITY
