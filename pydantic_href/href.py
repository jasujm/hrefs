"""Model references"""

import pydantic


class Href:
    """Hypertext reference to another model

    Arguments:
      key: the key used by the application to identify the model internally
      url: the URL identifying the model externally (e.g. via REST API)
    """

    def __init__(self, key: int, url: pydantic.AnyHttpUrl):
        self._key = key
        self._url = url

    def get_key(self):
        """Return the key of the referred object"""
        return self._key

    def get_url(self):
        """Return the URL of the referred object"""
        return self._url

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value):
        """Validate reference

        A reference can either be parsed from key or URL.

        Arguments:
          value: key or URL

        Return:
          A ``Href`` object referring to the model identified by the ``value``
          argument
        """
        if isinstance(value, int):
            return cls(key=value, url=f"/{value}")
        if isinstance(value, str):
            return cls(key=int(value.split("/")[-1]), url=value)
        raise TypeError(f"{value} is not int or str")
