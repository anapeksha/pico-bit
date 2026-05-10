"""Compatibility shim for older imports.

The build helpers now live in ``scripts.build_pipeline``. Keep this module as a
thin re-export so tests and older call sites continue to work during the
transition.
"""

from .build_pipeline import *  # noqa: F403
