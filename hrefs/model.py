"""Base models for referring and referrable types"""

import typing

import pydantic

from .href import Href, Referrable


if typing.TYPE_CHECKING:
    # `mypy` doesn't accept the true metaclass. should be investigated later.
    class BaseReferrableModel(pydantic.BaseModel, Referrable):
        """Dummy"""


else:
    # pylint: disable-all
    class _ReferrableModelMeta(pydantic.BaseModel.__class__, Referrable.__class__):
        pass

    class BaseReferrableModel(
        pydantic.BaseModel, Referrable, metaclass=_ReferrableModelMeta
    ):
        """Referrable model with pydantic integration

        A subclass of both :class:`pydantic.BaseModel` and
        :class:`hrefs.Referrable`.  It should be used as the base class of any
        pydantic model that will be used as target of :class:`hrefs.Href`.

        When using referrable models with FastAPI or Starlette in particular,
        :class:`hrefs.starlette.ReferrableModel` is more natural base.
        """
