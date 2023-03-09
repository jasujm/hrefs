.. _testing:

Testing
=======

``hypothesis`` integration
--------------------------

``hrefs`` uses the `hypothesis <https://hypothesis.readthedocs.io/en/latest/>`_
library to testing internally, and includes a hypothesis plugin for generating
:class:`hrefs.Href` instances. Thanks to the `entry points
<https://hypothesis.readthedocs.io/en/latest/strategies.html#entry-points>`_
mechanism, you don't need to do anything except ``import hypothesis`` and start
generating hyperlinks:

.. code-block:: python

   from dataclasses import dataclass
   from hrefs import Href, Referrable
   from hypothesis import given, strategies as st

   @dataclass
   class Book(Referrable):
       id: int

       def get_key(self) -> int:
           return self.id

       @staticmethod
       def key_to_url(key: int) -> str:
           return f"/books/{key}"

       @staticmethod
       def url_to_key(url: str):
           return int(url.split("/")[-1])

   @given(st.from_type(Href[Book]))
   def test_hrefs_with_hypothesis(href):
       assert isinstance(href, Href)
       assert href.url == f"/books/{href.key}"

Using ``hypothesis`` with FastAPI/Starlette
-------------------------------------------

Generating URLs for hyperlinks in FastAPI/Starlette normally relies on
:class:`hrefs.starlette.HrefMiddleware` to expose the request context to the
library. But the middleware doesn't directly work with the ``@given`` decorator,
since that would require ``hypothesis`` to run inside your Starlette
application. But ``hypothesis`` already wants to generate the data before your
test case even takes over.

In order to give ``hypothesis`` the context, you can use fixtures. Here is an
example using `pytest <https://docs.pytest.org/>`_:

.. code-block:: python

   from pytest import fixture
   from fastapi import FastAPI
   from hrefs import BaseReferrableModel
   from hrefs.starlette import href_context
   from hypothesis import given, strategies as st

   app = FastAPI(...)

   class Book(BaseReferrableModel):
       id: int

       # ...the rest of the definitions...

   @fixture(scope="module", autouse=True)
   def appcontext():
       with href_context(app, base_url="http://testserver"):
           yield

   @given(st.from_type(Href[Book]))
   def test_hrefs_with_hypothesis(href):
       assert isinstance(href, Href)
       assert href.url == f"http://testserver/books/{href.key}"

The example uses a module-scoped fixture. There is nothing wrong in using
function-scoped fixtures, but they are unnecessarily granular and `hypothesis
will warn against them by default
<https://hypothesis.readthedocs.io/en/latest/healthchecks.html#hypothesis.HealthCheck.function_scoped_fixture>`_.
