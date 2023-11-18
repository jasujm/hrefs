"""Hyperlinks for pydantic models"""

__version__ = "0.12"

from .href import Href, Referrable
from .model import BaseReferrableModel, PrimaryKey, HrefsConfigDict
from .errors import ReferrableModelError
