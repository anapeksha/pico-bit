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

OverrideValue: TypeAlias = object
ModuleOverrides: TypeAlias = dict[str, dict[str, OverrideValue]]
PAYLOAD_SEED_FILE = 'payload.dd'
PAYLOAD_LIBRARY_REPO = 'https://github.com/hak5/usbrubberducky-payloads.git'
PAYLOAD_LIBRARY_CHECKOUT = 'hak5-usbrubberducky-payloads'
PAYLOAD_LIBRARY_SUBTREE = Path('payloads') / 'library'
PAYLOAD_LIBRARY_FILENAMES = {'payload.dd', 'payload.txt'}
UNSAFE_LIBRARY_COMMANDS = {
    'ATTACKMODE',
    'EXFIL',
    'HIDE_PAYLOAD',
    'RESTORE_ATTACKMODE',
    'RESTORE_HOST_KEYBOARD_LOCK_STATE',
    'RESTORE_PAYLOAD',
    'SAVE_ATTACKMODE',
    'SAVE_HOST_KEYBOARD_LOCK_STATE',
    'WAIT_FOR_CAPS_CHANGE',
    'WAIT_FOR_CAPS_OFF',
    'WAIT_FOR_CAPS_ON',
    'WAIT_FOR_NUM_CHANGE',
    'WAIT_FOR_NUM_OFF',
    'WAIT_FOR_NUM_ON',
    'WAIT_FOR_SCROLL_CHANGE',
    'WAIT_FOR_SCROLL_OFF',
    'WAIT_FOR_SCROLL_ON',
}
UNSAFE_LIBRARY_INTERNALS = {
    '_CAPSLOCK_ON',
    '_NUMLOCK_ON',
    '_SCROLLLOCK_ON',
    '_EXFIL_MODE_ENABLED',
    '_EXFIL_BUFFER_FULL',
    '_EXFIL_LEDS_ENABLED',
    '_HOST_CONFIGURATION_REQUEST_COUNT',
    '_OS',
    '_STORAGE_ACTIVITY_TIMEOUT',
}
UNSAFE_LIBRARY_PREFIXES = ('_CAPSLOCK_', '_NUMLOCK_', '_SCROLLLOCK_', '_EXFIL_')
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
                node.value = _literal_node(self._overrides[name])
        return self.generic_visit(node)

    def visit_AnnAssign(self, node):
        if isinstance(node.target, ast.Name) and node.target.id in self._overrides:
            node.value = _literal_node(self._overrides[node.target.id])
        return self.generic_visit(node)


def _literal_node(value: OverrideValue) -> ast.expr:
    return ast.parse(repr(value), mode='eval').body


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


def payload_seed_text(root: Path) -> str:
    return (root / PAYLOAD_SEED_FILE).read_text(encoding='utf-8')


def _is_ducky_comment(text: str) -> bool:
    upper = text.upper()
    return upper == 'REM' or upper.startswith('REM ') or upper.startswith('//')


def _apply_defines(line: str, defines: dict[str, str]) -> str:
    for key, value in defines.items():
        if key in line:
            line = line.replace(key, value)
    return line


def _unsafe_variable_references(text: str) -> bool:
    index = 0
    while index < len(text):
        if text[index] != '$':
            index += 1
            continue

        if index + 1 < len(text) and text[index + 1] == '$':
            index += 2
            continue

        start = index + 1
        if start >= len(text):
            break

        if not (text[start].isalpha() or text[start] == '_'):
            index += 1
            continue

        end = start + 1
        while end < len(text) and (text[end].isalnum() or text[end] == '_'):
            end += 1

        name = text[start:end]
        if name in UNSAFE_LIBRARY_INTERNALS or name.startswith(UNSAFE_LIBRARY_PREFIXES):
            return True

        index = end

    return False


def payload_uses_unsafe_features(script: str) -> bool:
    defines: dict[str, str] = {}
    in_rem_block = False
    string_block_end = ''

    for raw_line in script.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        stripped = raw_line.strip()
        upper = stripped.upper()

        if in_rem_block:
            if upper in ('END_REM', 'ENDREM'):
                in_rem_block = False
            continue

        if string_block_end:
            if upper == string_block_end:
                string_block_end = ''
                continue
            if _unsafe_variable_references(raw_line):
                return True
            continue

        if upper == 'REM_BLOCK':
            in_rem_block = True
            continue

        if not stripped or _is_ducky_comment(stripped):
            continue

        if upper.startswith('DEFINE '):
            parts = stripped.split(None, 2)
            if len(parts) == 3:
                defines[parts[1]] = parts[2]
            continue

        line = _apply_defines(raw_line.rstrip(), defines)
        stripped = line.strip()
        upper = stripped.upper()
        if not stripped or _is_ducky_comment(stripped):
            continue

        if upper == 'STRING':
            string_block_end = 'END_STRING'
            continue

        if upper == 'STRINGLN':
            string_block_end = 'END_STRINGLN'
            continue

        keyword = stripped.split(None, 1)[0].upper()
        if keyword in UNSAFE_LIBRARY_COMMANDS:
            return True

        if _unsafe_variable_references(line):
            return True

    return False


def _payload_repo_dir(build_dir: Path) -> Path:
    return build_dir / PAYLOAD_LIBRARY_CHECKOUT


def _clone_payload_library_repo(repo_dir: Path) -> None:
    subprocess.run(
        [
            'git',
            'clone',
            '--depth',
            '1',
            '--filter=blob:none',
            '--sparse',
            PAYLOAD_LIBRARY_REPO,
            str(repo_dir),
        ],
        check=True,
    )
    subprocess.run(
        ['git', '-C', str(repo_dir), 'sparse-checkout', 'set', str(PAYLOAD_LIBRARY_SUBTREE)],
        check=True,
    )


def _ensure_payload_library_repo(build_dir: Path) -> Path | None:
    repo_dir = _payload_repo_dir(build_dir)
    library_root = repo_dir / PAYLOAD_LIBRARY_SUBTREE
    if library_root.exists():
        return repo_dir

    try:
        if repo_dir.exists():
            subprocess.run(
                [
                    'git',
                    '-C',
                    str(repo_dir),
                    'sparse-checkout',
                    'set',
                    str(PAYLOAD_LIBRARY_SUBTREE),
                ],
                check=True,
            )
        else:
            build_dir.mkdir(parents=True, exist_ok=True)
            _clone_payload_library_repo(repo_dir)
    except (OSError, subprocess.CalledProcessError):
        return None

    if library_root.exists():
        return repo_dir
    return None


def _payload_file_priority(path: Path) -> tuple[int, str]:
    name = path.name.lower()
    return (0 if name == 'payload.dd' else 1, name)


def _humanize_payload_label(segment: str) -> str:
    cleaned = segment.replace('_', ' ').replace('-', ' ').strip()
    if not cleaned:
        return segment
    if cleaned.lower() == cleaned:
        return cleaned.title()
    return cleaned


def discover_payload_library_entries(
    library_root: Path,
) -> tuple[tuple[str, str, str, str, bool, str], ...]:
    discovered: dict[str, tuple[Path, tuple[str, str, str, str, bool, str]]] = {}

    for path in sorted(library_root.rglob('*')):
        if not path.is_file() or path.name.lower() not in PAYLOAD_LIBRARY_FILENAMES:
            continue

        relative_parent = path.relative_to(library_root).parent
        if not relative_parent.parts:
            continue

        group_key = relative_parent.parts[0]
        group_label = _humanize_payload_label(group_key)
        label_parts = relative_parent.parts[1:] or relative_parent.parts[-1:]
        label = ' / '.join(_humanize_payload_label(part) for part in label_parts)
        payload_id = '/'.join(relative_parent.parts)
        script = path.read_text(encoding='utf-8', errors='ignore')
        script = script.replace('\r\n', '\n').replace('\r', '\n')
        entry = (
            payload_id,
            group_key,
            group_label,
            label,
            not payload_uses_unsafe_features(script),
            script,
        )
        current = discovered.get(payload_id)
        if current is None or _payload_file_priority(path) < _payload_file_priority(current[0]):
            discovered[payload_id] = (path, entry)

    ordered = sorted(
        (entry for _path, entry in discovered.values()),
        key=lambda entry: (entry[1], entry[3].lower(), entry[0]),
    )
    return tuple(ordered)


def baked_payload_library_entries(
    root: Path,
    *,
    build_dir: Path | None = None,
) -> tuple[tuple[str, str, str, str, bool, str], ...]:
    if not (root / 'src' / 'payload_library.py').exists():
        return ()

    repo_dir = _ensure_payload_library_repo(build_dir or (root / '.build'))
    if repo_dir is None:
        return ()

    library_root = repo_dir / PAYLOAD_LIBRARY_SUBTREE
    if not library_root.exists():
        return ()

    try:
        return discover_payload_library_entries(library_root)
    except OSError:
        return ()


def build_module_overrides(
    root: Path,
    *,
    build_dir: Path | None = None,
    device_config_overrides: dict[str, OverrideValue] | None = None,
) -> ModuleOverrides:
    overrides: ModuleOverrides = {
        'ducky.constants': {
            'DEFAULT_PAYLOAD': payload_seed_text(root),
        }
    }
    if (root / 'src' / 'payload_library.py').exists():
        overrides['payload_library'] = {
            'PAYLOAD_LIBRARY': baked_payload_library_entries(root, build_dir=build_dir),
        }
    if device_config_overrides:
        overrides['device_config'] = dict(device_config_overrides)
    return overrides


def render_module_source(source: str, overrides: dict[str, OverrideValue]) -> str:
    if not overrides:
        return source
    tree = ast.parse(source)
    updated = OverrideInjector(overrides).visit(tree)
    ast.fix_missing_locations(updated)
    return ast.unparse(updated) + '\n'


def render_device_config(source: str, overrides: dict[str, OverrideValue]) -> str:
    return render_module_source(source, overrides)


def _module_source_path(source_root: Path, module_name: str) -> Path:
    parts = module_name.split('.')
    module_path = source_root.joinpath(*parts)
    package_init = module_path / '__init__.py'
    if package_init.exists():
        return package_init

    module_file = module_path.with_suffix('.py')
    if module_file.exists():
        return module_file

    raise FileNotFoundError(f'module {module_name!r} not found under {source_root}')


def prepare_source_tree(
    *,
    build_dir: Path,
    root_src_dir: Path,
    overrides_by_module: ModuleOverrides | None = None,
) -> Path:
    build_dir.mkdir(exist_ok=True)
    sync_web_assets()
    source_root = Path(tempfile.mkdtemp(prefix='pico-bit-src-', dir=build_dir))
    configured_src = source_root / 'src'
    shutil.copytree(root_src_dir, configured_src)

    if overrides_by_module:
        for module_name, overrides in overrides_by_module.items():
            module_path = _module_source_path(configured_src, module_name)
            source = module_path.read_text(encoding='utf-8')
            module_path.write_text(
                render_module_source(source, overrides),
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
        source_name = source.relative_to(source_dir).as_posix()
        relative = source.relative_to(source_dir).with_suffix('.mpy')
        output = output_dir / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [*compiler_cmd, '-s', source_name, '-o', str(output), str(source)],
            cwd=cwd,
            check=True,
        )
        compiled.append(output)
    return compiled
