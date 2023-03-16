"""
Integration test with the test application

This module contains a `stateful test
<https://hypothesis.readthedocs.io/en/latest/stateful.html>`_ using the test
application in various ways to exercise the ``hrefs`` library.

This is slow, so only ran if ``--slow`` option is given to ``pytest``.
"""

import itertools

from fastapi.testclient import TestClient
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, Bundle, rule
import pytest

from app import app


class AppStateMachine(RuleBasedStateMachine):
    """Rule based state machine for the test application"""

    def __init__(self):
        super().__init__()
        self.client = TestClient(app)

    books: Bundle = Bundle("books")
    libraries: Bundle = Bundle("libraries")

    @rule(target=books, title=st.text())
    def create_book(self, title):
        """Create book via API"""
        response = self.client.post("/books", json={"title": title})
        assert response.status_code == 201
        url = response.headers["Location"]
        return url, title

    @rule(book=books)
    def read_book(self, book):
        """Read book via API"""
        url, title = book
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.json() == {"self": url, "title": title}

    @rule(book_id=st.uuids())
    def read_nonexistent_book(self, book_id):
        """Try to read nonexistent book"""
        response = self.client.get(f"/books/{book_id}")
        assert response.status_code == 404

    @rule(target=libraries, books_by_url=st.lists(books), books_by_id=st.lists(books))
    def create_library(self, books_by_url, books_by_id):
        """Create library via API"""
        book_urls = [book[0] for book in itertools.chain(books_by_url, books_by_id)]
        response = self.client.post(
            "/libraries",
            json={
                "books": [
                    *(book[0] for book in books_by_url),
                    *(book[0].split("/")[-1] for book in books_by_id),
                ]
            },
        )
        assert response.status_code == 201
        url = response.headers["Location"]
        return url, book_urls

    @rule(books=st.lists(books), nonexistent_books=st.lists(st.uuids(), min_size=1))
    def create_library_with_nonexistent_books(self, books, nonexistent_books):
        """Try to create a library with nonexistent books"""
        response = self.client.post(
            "/libraries",
            json={
                "books": [
                    *(book[0] for book in books),
                    *(str(book) for book in nonexistent_books),
                ]
            },
        )
        assert response.status_code == 400

    @rule(library=libraries)
    def read_library(self, library):
        """Read library via API"""
        url, books = library
        response = self.client.get(url)
        assert response.status_code == 200
        assert response.json() == {"self": url, "books": books}

    @rule(library_id=st.uuids())
    def read_nonexistent_library(self, library_id):
        """Try to read nonexistent library"""
        response = self.client.get(f"/libraries/{library_id}")
        assert response.status_code == 404


TestApp = pytest.mark.slow(AppStateMachine.TestCase)
