"""Tooling modules for local builds and release packaging."""

from __future__ import annotations

__all__ = ['run_build', 'run_deploy']


def run_build(*args, **kwargs):
    from .build import run_build as _run_build

    return _run_build(*args, **kwargs)


def run_deploy(*args, **kwargs):
    from .deploy import run_deploy as _run_deploy

    return _run_deploy(*args, **kwargs)
