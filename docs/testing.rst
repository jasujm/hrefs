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

   from hrefs import Href, BaseReferrableModel
   from hypothesis import given, strategies as st

   class Book(BaseReferrableModel):
       id: int

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
library. This is usually no issue in request handlers, but may become an
obstacle when trying to generate hyperlinks with the ``@given``
decorator. That's because the decorator applies to the test case defined at the
module level --- not inside a request handler!

You can use :func:`hrefs.starlette.href_context()` to set the application under
test to be the hyperlink context. Wrapping this in a fixture enables ``@given``
to do its magic for hyperlinks. Here is an example using `pytest
<https://docs.pytest.org/>`_:

.. code-block:: python

   from pytest import fixture
   from fastapi import FastAPI
   from hrefs.starlette import ReferrableModel, href_context
   from hypothesis import given, strategies as st, settings, HealthCheck

   app = FastAPI(...)

   class Book(ReferrableModel):
       id: int

       # ...the rest of the definitions...

   @fixture
   def appcontext():
       with href_context(app, base_url="http://testserver"):
           yield  # see https://docs.pytest.org/en/7.1.x/how-to/fixtures.html#yield-fixtures-recommended

   @given(st.from_type(Href[Book]))
   @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
   def test_hrefs_with_hypothesis(href):
       assert href.url == f"http://testserver/books/{href.key}"
