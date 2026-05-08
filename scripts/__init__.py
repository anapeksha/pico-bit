"""Tooling modules for local builds and release packaging."""

from __future__ import annotations

__all__ = ['run_build', 'run_release']


def run_build(*args, **kwargs):
    from .build import run_build as _run_build

    return _run_build(*args, **kwargs)


def run_release(*args, **kwargs):
    from .release import run_release as _run_release

    return _run_release(*args, **kwargs)
