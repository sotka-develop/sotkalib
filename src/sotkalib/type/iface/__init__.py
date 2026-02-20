"""module containing utilities for runtime type-checking and protocol inference"""

from ._compat import compatible
from ._error import DoesNotImplementError
from ._impl import implements
from ._proto_mixin import CheckableProtocol

__all__ = ("CheckableProtocol", "DoesNotImplementError", "implements", "compatible")
