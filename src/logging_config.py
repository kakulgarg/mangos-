"""
Central logging setup. One call, `get_logger(__name__)`, everywhere -- so the
whole pipeline shares one timestamped, levelled format instead of scattered
print statements.
"""

from __future__ import annotations

import logging
import sys

_CONFIGURED = False
_FMT = "%(asctime)s  %(levelname)-7s  %(name)-18s  %(message)s"
_DATEFMT = "%H:%M:%S"


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a module logger, configuring the root handler once."""
    global _CONFIGURED
    if not _CONFIGURED:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
        root = logging.getLogger()
        root.addHandler(handler)
        root.setLevel(level)
        _CONFIGURED = True
    return logging.getLogger(name)
