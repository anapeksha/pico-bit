from __future__ import annotations

import argparse
import ast
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TypeAlias

from .asset_pipeline import sync_web_assets

OverrideValue: TypeAlias = str | bool | int | float | complex | bytes | None
OVERRIDE_ENV = {
    'ALLOW_UNSAFE': 'PICO_BIT_ALLOW_UNSAFE',
    'AP_PASSWORD': 'PICO_BIT_AP_PASSWORD',
    'AP_SSID': 'PICO_BIT_AP_SSID',
    'CORS_ALLOW_CREDENTIALS': 'PICO_BIT_CORS_ALLOW_CREDENTIALS',
    'CORS_ALLOWED_ORIGIN': 'PICO_BIT_CORS_ALLOWED_ORIGIN',
    'PORTAL_AUTH_ENABLED': 'PICO_BIT_PORTAL_AUTH_ENABLED',
    'PORTAL_PASSWORD': 'PICO_BIT_PORTAL_PASSWORD',
    'PORTAL_USERNAME': 'PICO_BIT_PORTAL_USERNAME',
}


class OverrideInjector(ast.NodeTransformer):
    def __init__(self, overrides: dict[str, OverrideValue]) -> None:
        self._overrides = overrides

    def visit_Assign(self, node):
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in self._overrides:
                node.value = ast.Constant(value=self._overrides[name])
        return self.generic_visit(node)

    def visit_AnnAssign(self, node):
        if isinstance(node.target, ast.Name) and node.target.id in self._overrides:
            node.value = ast.Constant(value=self._overrides[node.target.id])
        return self.generic_visit(node)


def optional_env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None:
        return None
    return value.strip()


def parse_bool_flag(raw_value: str, label: str) -> bool | None:
    value = raw_value.strip().lower()
    if value in {'1', 'true', 'yes', 'on'}:
        return True
    if value in {'0', 'false', 'no', 'off'}:
        return False
    if value == 'default':
        return None
    raise ValueError(f'{label} must be one of: true, false, 1, 0, yes, no, on, off, default')


def validate_config_value(name: str, value: OverrideValue) -> None:
    if not isinstance(value, str):
        return
    if name == 'AP_SSID' and not 1 <= len(value) <= 32:
        raise ValueError('AP SSID must be between 1 and 32 characters')
    if name == 'AP_PASSWORD' and value != '' and not 8 <= len(value) <= 63:
        raise ValueError('AP password must be blank or between 8 and 63 characters')
    if name == 'PORTAL_USERNAME' and not value:
        raise ValueError('Portal username cannot be blank')
    if name == 'PORTAL_PASSWORD' and value == '':
        raise ValueError('Portal password cannot be blank when explicitly overridden')


def config_value(args: argparse.Namespace, arg_name: str, key: str) -> str | None:
    value = getattr(args, arg_name)
    if value is not None:
        return value
    return optional_env(OVERRIDE_ENV[key])


def build_config_overrides(args: argparse.Namespace) -> dict[str, OverrideValue]:
    raw_strings = {
        'AP_SSID': config_value(args, 'ap_ssid', 'AP_SSID'),
        'AP_PASSWORD': config_value(args, 'ap_password', 'AP_PASSWORD'),
        'PORTAL_USERNAME': config_value(args, 'portal_username', 'PORTAL_USERNAME'),
        'PORTAL_PASSWORD': config_value(args, 'portal_password', 'PORTAL_PASSWORD'),
        'CORS_ALLOWED_ORIGIN': config_value(args, 'cors_allowed_origin', 'CORS_ALLOWED_ORIGIN'),
    }
    raw_bools = {
        'ALLOW_UNSAFE': config_value(args, 'allow_unsafe', 'ALLOW_UNSAFE'),
        'PORTAL_AUTH_ENABLED': config_value(
            args,
            'portal_auth_enabled',
            'PORTAL_AUTH_ENABLED',
        ),
        'CORS_ALLOW_CREDENTIALS': config_value(
            args,
            'cors_allow_credentials',
            'CORS_ALLOW_CREDENTIALS',
        ),
    }

    overrides: dict[str, OverrideValue] = {}
    for key, value in raw_strings.items():
        if value is None:
            continue
        validate_config_value(key, value)
        overrides[key] = value

    for key, value in raw_bools.items():
        if value is None:
            continue
        parsed = parse_bool_flag(value, key.lower().replace('_', '-'))
        if parsed is None:
            continue
        overrides[key] = parsed

    return overrides


def render_device_config(source: str, overrides: dict[str, OverrideValue]) -> str:
    if not overrides:
        return source
    tree = ast.parse(source)
    updated = OverrideInjector(overrides).visit(tree)
    ast.fix_missing_locations(updated)
    return ast.unparse(updated) + '\n'


def prepare_source_tree(
    *,
    build_dir: Path,
    root_src_dir: Path,
    overrides: dict[str, OverrideValue],
) -> Path:
    build_dir.mkdir(exist_ok=True)
    sync_web_assets()
    source_root = Path(tempfile.mkdtemp(prefix='pico-bit-src-', dir=build_dir))
    configured_src = source_root / 'src'
    shutil.copytree(root_src_dir, configured_src)

    if overrides:
        device_config = configured_src / 'device_config.py'
        source = device_config.read_text(encoding='utf-8')
        device_config.write_text(
            render_device_config(source, overrides),
            encoding='utf-8',
        )

    return configured_src


def source_modules(source_dir: Path) -> list[Path]:
    return sorted(
        path for path in source_dir.rglob('*.py') if '__pycache__' not in path.parts
    )


def clean_mpy_output(output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def build_mpy_tree(
    *,
    compiler_cmd: list[str],
    output_dir: Path,
    source_dir: Path,
    cwd: Path,
) -> list[Path]:
    clean_mpy_output(output_dir)

    compiled: list[Path] = []
    for source in source_modules(source_dir):
        relative = source.relative_to(source_dir).with_suffix('.mpy')
        output = output_dir / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([*compiler_cmd, str(source), '-o', str(output)], cwd=cwd, check=True)
        compiled.append(output)
    return compiled
