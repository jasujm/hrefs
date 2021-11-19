"""Base models for referring and referrable types"""

import operator
import typing

import pydantic

from .href import Href, Referrable


class BaseModel(pydantic.BaseModel):
    """pydantic model with href support

    This is a simple subclass of :class:`pydantic.BaseModel`. It is almost
    identical to its base class, but adds a custom JSON encoder to serialize
    :class:`hrefs.Href` objects into URLs.
    """

    class Config:
        """Common model configuration"""

        json_encoders = {Href: operator.attrgetter("url")}


if typing.TYPE_CHECKING:
    # `mypy` doesn't accept the true metaclass. should be investigated later.
    class BaseReferrableModel(BaseModel, Referrable):
        """Dummy"""


else:
    # pylint: disable-all
    class _ReferrableModelMeta(BaseModel.__class__, Referrable.__class__):
        pass

    class BaseReferrableModel(BaseModel, Referrable, metaclass=_ReferrableModelMeta):
        """Referrable model with pydantic integration

        A subclass of both :class:`hrefs.BaseModel` and
        :class:`hrefs.Referrable`.  It should be used as the base class of any
        pydantic model that will be used as target of :class:`hrefs.Href`.

        When using referrable models with FastAPI or Starlette in particular,
        :class:`hrefs.starlette.ReferrableModel` is more natural base.
        """
