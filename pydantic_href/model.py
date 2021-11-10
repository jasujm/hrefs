"""Pydantic model extensions"""

import pydantic

from .href import Href


class BaseModel(pydantic.BaseModel):
    """Pydantic model using href features"""

    class Config:
        """Common model configuration"""

        json_encoders = {Href: lambda h: h.get_url()}
