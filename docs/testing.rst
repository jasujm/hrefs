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

   class Book(ReferrableModel):
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
