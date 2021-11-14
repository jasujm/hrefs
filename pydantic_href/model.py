"""Base models for referring and referrable types"""

import typing

import pydantic

from .href import Href, Referrable


class BaseModel(pydantic.BaseModel):
    """Pydantic model using href features

    `BaseModel` ensures that models is using custom JSON encoder that serializes
    `Href` fields into URLs.
    """

    class Config:
        """Common model configuration"""

        json_encoders = {Href: lambda h: h.get_url()}


if typing.TYPE_CHECKING:
    # `mypy` doesn't accept the true metaclass. should be investigated later.
    class ReferrableModel(BaseModel, Referrable):
        """Dummy"""

else:
    # pylint: disable-all
    class _ReferrableModelMeta(BaseModel.__class__, Referrable.__class__):
        pass

    class ReferrableModel(BaseModel, Referrable, metaclass=_ReferrableModelMeta):
        """Referrable model with pydantic integration

        This is an abstract base class that inherits both `BaseModel` and
        (partially) implements the `Referrable` protocol. The subclass needs to
        implement `key_to_url()` and `url_to_key()` as described in the
        documentation of `Referrable`.

        `ReferrableModel` inherits `href.BaseModel`, ensuring that the custom
        `Href` `json_encoder` is used to serialize references.
        """
