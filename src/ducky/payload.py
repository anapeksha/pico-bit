"""
Payload file discovery helpers.
"""

import os

from .constants import PAYLOAD_FILE


def _join_path(base, name):
    if base in ('', '.'):
        return name
    if base.endswith('/'):
        return base + name
    return base + '/' + name


def _safe_listdir(path):
    try:
        return os.listdir(path)
    except OSError:
        return None


def _find_payload_in(path, seen):
    if path in seen:
        return None
    seen[path] = True

    entries = _safe_listdir(path)
    if entries is None:
        return None

    for name in entries:
        if name.lower() == PAYLOAD_FILE:
            return _join_path(path, name)

    for name in entries:
        child = _join_path(path, name)
        if _safe_listdir(child) is not None:
            found = _find_payload_in(child, seen)
            if found:
                return found
    return None


def find_payload(start='.'):
    for candidate in (PAYLOAD_FILE, _join_path(start, PAYLOAD_FILE)):
        try:
            with open(candidate):
                return candidate
        except OSError:
            pass
    return _find_payload_in(start, {})
