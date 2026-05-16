import asyncio
import gc
import json

from device_config import AP_PASSWORD, AP_SSID
from ducky import (
    DEFAULT_PAYLOAD,
    PAYLOAD_FILE,
    analyze_script,
    ensure_payload,
    find_payload,
)
from ducky.analysis import AnalysisResult
from keyboard import (
    DEFAULT_LAYOUT_CODE,
    compose_layout_code,
    default_layout_code,
    is_supported_layout,
    is_supported_platform,
    layout_option,
    normalize_layout_code,
    normalize_platform_code,
    split_layout_code,
    supported_layouts,
    supported_platforms,
)
from status_led import STATUS_LED

from .._http import _KEYBOARD_LAYOUT_FILE, _RUN_HISTORY_LIMIT, _ticks_ms
from ..execution_stream import ExecutionStreamState
from ..loot_crypto import decrypt, derive_key, encrypt

_PAYLOAD_KEY = derive_key(AP_SSID, AP_PASSWORD)

_BINARY_TARGET_OSES = {'windows', 'linux', 'macos'}


class _PayloadMixin:
    # Attributes provided by SetupServer.__init__
    _ap_ip: str
    _ap_password_in_use: str
    _keyboard_layout: str
    _keyboard_layout_state_cache: dict[str, object] | None
    _payload_seeded: bool
    _run_history: list[dict[str, object]]
    _run_sequence: int
    _execution_stream: ExecutionStreamState

    # Methods provided by SetupServer / other mixins
    def _auth_enabled(self) -> bool: ...
    def _is_authorized(self, request) -> bool: ...
    def _keyboard_ready(self) -> bool: ...
    def _has_binary(self) -> bool: ...
    def _binary_matches_target(self, target_os: str) -> bool: ...
    def _binary_target_notice(self, target_os: str) -> str: ...
    def _stager_script(self, target_os: str) -> str: ...
    def _usb_agent_state(self) -> dict[str, object]: ...
    async def _init_execution_loot(self, target_os: str) -> None: ...
    async def _handle_loot_get(self, request, writer) -> None: ...
    async def _handle_loot_download(self, request, writer) -> None: ...
    async def _handle_usb_loot_import(self, request, writer) -> None: ...
    async def _handle_execution_stream(self, request, writer) -> None: ...
    async def _handle_usb_agent(self, request, writer) -> None: ...
    async def _send(self, writer, request, status: str, body, headers=None) -> None: ...
    async def _send_json(self, writer, request, status: str, data: dict[str, object]) -> None: ...
    async def _run_payload(self, script: str, *, source: str = 'portal') -> tuple[str, str]: ...

    def _seed_payload(self) -> str:
        payload_path, created = ensure_payload(seed=DEFAULT_PAYLOAD)
        if created:
            self._payload_seeded = True
        return payload_path

    async def _read_payload(self) -> str:
        gc.collect()
        payload_path = self._seed_payload()
        try:
            with open(payload_path, 'rb') as f:
                data = f.read()
        except OSError:
            return DEFAULT_PAYLOAD
        if not data:
            return DEFAULT_PAYLOAD
        return await decrypt(data, _PAYLOAD_KEY)

    async def _write_payload(self, content: str) -> str:
        payload_path = find_payload() or PAYLOAD_FILE
        ciphertext = await encrypt(content, _PAYLOAD_KEY)
        with open(payload_path, 'wb') as f:
            f.write(ciphertext)
        self._payload_seeded = False
        return payload_path

    def _load_keyboard_layout(self) -> str:
        try:
            with open(_KEYBOARD_LAYOUT_FILE) as f:
                raw = f.read().strip()
        except OSError:
            raw = ''

        normalized = normalize_layout_code(raw or self._keyboard_layout)
        if normalized not in {item['code'] for item in supported_layouts()}:
            normalized = DEFAULT_LAYOUT_CODE
        self._keyboard_layout = normalized
        return self._keyboard_layout

    def _persist_keyboard_layout(self, code: str) -> None:
        with open(_KEYBOARD_LAYOUT_FILE, 'w') as f:
            f.write(code + '\n')

    def _set_keyboard_layout(self, code: str, *, persist: bool = False) -> str:
        normalized = normalize_layout_code(code)
        if not is_supported_layout(normalized):
            raise ValueError('unsupported keyboard layout')
        self._keyboard_layout = normalized
        self._keyboard_layout_state_cache = None
        if persist:
            self._persist_keyboard_layout(normalized)
        return normalized

    def _keyboard_layout_state(self) -> dict[str, object]:
        if self._keyboard_layout_state_cache is not None:
            return self._keyboard_layout_state_cache
        option = layout_option(self._keyboard_layout)
        platform, layout = split_layout_code(self._keyboard_layout)
        target_label = option['platform_label'] + ' · ' + option['label']
        self._keyboard_layout_state_cache = {
            'keyboard_layout': layout,
            'keyboard_layout_code': layout,
            'keyboard_layout_hint': 'Used for typed text and remembered on the device.',
            'keyboard_layout_label': option['label'],
            'keyboard_layout_platform': option['platform'],
            'keyboard_layout_profile': option['code'],
            'keyboard_layout_profile_code': option['code'],
            'keyboard_layout_short': option['layout'],
            'keyboard_layouts': supported_layouts(platform),
            'keyboard_os': platform,
            'keyboard_os_code': platform,
            'keyboard_os_label': option['platform_label'],
            'keyboard_oses': supported_platforms(),
            'keyboard_target_label': target_label,
        }
        return self._keyboard_layout_state_cache

    def _validation_state(self, script: str) -> AnalysisResult:
        return analyze_script(script)

    def _history_preview(self, script: str) -> str:
        for raw_line in script.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
            stripped = raw_line.strip()
            upper = stripped.upper()
            if not stripped or upper == 'REM' or upper.startswith('REM ') or upper.startswith('//'):
                continue
            if len(stripped) > 72:
                return stripped[:69] + '...'
            return stripped
        return 'Empty payload'

    def _recent_runs(self) -> list[dict[str, object]]:
        return list(self._run_history)

    def _record_run(self, script: str, message: str, notice: str, *, source: str) -> None:
        self._run_sequence += 1
        self._run_history.insert(
            0,
            {
                'at_ms': _ticks_ms(),
                'message': message,
                'notice': notice,
                'preview': self._history_preview(script),
                'sequence': self._run_sequence,
                'source': source,
            },
        )
        del self._run_history[_RUN_HISTORY_LIMIT:]

    def record_run(self, script: str, message: str, notice: str, *, source: str) -> None:
        self._record_run(script, message, notice, source=source)

    async def _run_binary_injection(self, target_os: str) -> None:
        """Background task: type the stager script via HID and publish execution events.

        Called via asyncio.create_task so /api/inject_binary can return 200 OK
        immediately without blocking the HTTP connection while HID typing runs.
        """
        try:
            await STATUS_LED.show('binary_injecting')
            script = self._stager_script(target_os)
            message, notice = await self._run_payload(script, source='binary:usb')
        except Exception as exc:  # noqa: BLE001
            message = f'Runtime error: {type(exc).__name__}'
            notice = 'error'

        if notice == 'success':
            self._execution_stream.publish('Copy', 'success')
            self._execution_stream.publish('Execute', 'loading')
        else:
            self._execution_stream.publish('Copy', 'error', reason=message)
            try:
                await STATUS_LED.show('binary_inject_failed')
            except Exception:  # noqa: BLE001
                pass

    async def _bootstrap_state(self) -> dict[str, object]:
        message = ''
        notice = 'quiet'
        if self._payload_seeded:
            message = 'payload.dd was seeded on this boot.'
        payload = await self._read_payload()

        state = {
            'ap_ip': self._ap_ip,
            'ap_password': self._ap_password_in_use or 'Open network',
            'ap_ssid': AP_SSID,
            'auth_enabled': self._auth_enabled(),
            'keyboard_ready': self._keyboard_ready(),
            'message': message,
            'notice': notice,
            'payload': payload,
            'run_history': self._recent_runs(),
            'seeded': self._payload_seeded,
            'has_binary': self._has_binary(),
            'usb_agent': self._usb_agent_state(),
        }
        state.update(self._keyboard_layout_state())
        return state

    async def _handle_api(self, request, writer) -> None:
        if not self._is_authorized(request):
            await self._send_json(
                writer,
                request,
                '401 Unauthorized',
                {'message': 'Sign in required.'},
            )
            return

        if request['method'] == 'GET' and request['path'] == '/api/bootstrap':
            await asyncio.sleep(0)
            state = await self._bootstrap_state()
            await self._send_json(writer, request, '200 OK', state)
            return

        if request['method'] == 'POST' and request['path'] == '/api/payload':
            data = json.loads(request['body'].decode('utf-8', 'ignore') or '{}')
            payload = str(data.get('payload', '')).replace('\r\n', '\n')
            await asyncio.sleep(0)
            validation = self._validation_state(payload)
            if validation['blocking']:
                await self._send_json(
                    writer,
                    request,
                    '400 Bad Request',
                    {
                        'message': validation['summary'],
                        'notice': 'error',
                        'validation': validation,
                    },
                )
                return

            await asyncio.sleep(0)
            await self._write_payload(payload)
            await self._send_json(
                writer,
                request,
                '200 OK',
                {
                    'message': 'payload.dd saved.',
                    'notice': 'success',
                    'validation': validation,
                },
            )
            return

        if request['method'] == 'POST' and request['path'] == '/api/validate':
            data = json.loads(request['body'].decode('utf-8', 'ignore') or '{}')
            payload = str(data.get('payload', '')).replace('\r\n', '\n')
            await asyncio.sleep(0)
            validation = self._validation_state(payload)
            await self._send_json(
                writer,
                request,
                '200 OK',
                {
                    'message': validation['summary'],
                    'notice': validation['notice'],
                    'validation': validation,
                },
            )
            return

        if request['method'] == 'POST' and request['path'] == '/api/keyboard-layout':
            data = json.loads(request['body'].decode('utf-8', 'ignore') or '{}')
            requested_os = data.get('os')
            requested_layout = data.get('layout')
            current_os, _current_layout = split_layout_code(self._keyboard_layout)

            if requested_os is not None and not is_supported_platform(str(requested_os)):
                response_payload: dict[str, object] = {
                    'message': 'Unsupported operating system.',
                    'notice': 'error',
                }
                response_payload.update(self._keyboard_layout_state())
                await self._send_json(
                    writer,
                    request,
                    '400 Bad Request',
                    response_payload,
                )
                return

            platform = normalize_platform_code(str(requested_os or current_os))
            layout_text = str(requested_layout or '').strip()
            if layout_text:
                normalized = compose_layout_code(platform, layout_text)
                if not is_supported_layout(normalized):
                    platform_label = layout_option(default_layout_code(platform))['platform_label']
                    response_payload: dict[str, object] = {
                        'message': f'Unsupported keyboard layout for {platform_label}.',
                        'notice': 'error',
                    }
                    response_payload.update(self._keyboard_layout_state())
                    await self._send_json(
                        writer,
                        request,
                        '400 Bad Request',
                        response_payload,
                    )
                    return
            else:
                normalized = default_layout_code(platform)

            self._set_keyboard_layout(normalized, persist=True)
            await STATUS_LED.show('keyboard_layout_changed')
            option = layout_option(normalized)
            response_payload: dict[str, object] = {
                'message': f'Typing target set to {option["platform_label"]} · {option["label"]}.',
                'notice': 'success',
            }
            response_payload.update(self._keyboard_layout_state())
            await self._send_json(
                writer,
                request,
                '200 OK',
                response_payload,
            )
            return

        if request['method'] == 'POST' and request['path'] == '/api/run':
            data = json.loads(request['body'].decode('utf-8', 'ignore') or '{}')
            await asyncio.sleep(0)
            payload_raw = data.get('payload')
            if payload_raw is None:
                payload_raw = await self._read_payload()
            payload = str(payload_raw).replace('\r\n', '\n')
            await asyncio.sleep(0)
            validation = self._validation_state(payload)
            if validation['blocking']:
                await self._send_json(
                    writer,
                    request,
                    '400 Bad Request',
                    {
                        'message': validation['summary'],
                        'notice': 'error',
                        'validation': validation,
                    },
                )
                return

            if data.get('save', True):
                await asyncio.sleep(0)
                await self._write_payload(payload)
            message, notice = await self._run_payload(payload)
            status = '200 OK' if notice == 'success' else '400 Bad Request'
            await self._send_json(
                writer,
                request,
                status,
                {
                    'message': message,
                    'notice': notice,
                    'run_history': self._recent_runs(),
                    'validation': validation,
                },
            )
            return

        path = request['path']
        method = request['method']

        if path == '/api/loot' and method == 'GET':
            await self._handle_loot_get(request, writer)
            return

        if path == '/api/loot/download' and method == 'GET':
            await self._handle_loot_download(request, writer)
            return

        if path == '/api/loot/import-usb' and method == 'POST':
            await self._handle_usb_loot_import(request, writer)
            return

        if path == '/api/usb-agent':
            await self._handle_usb_agent(request, writer)
            return

        if path == '/api/inject_binary' and method == 'POST':
            if not self._has_binary():
                await self._send_json(
                    writer,
                    request,
                    '404 Not Found',
                    {'message': 'No binary uploaded yet.', 'notice': 'error'},
                )
                return
            try:
                data = json.loads(request['body'].decode('utf-8', 'ignore') or '{}')
            except ValueError:
                data = {}
            target_os = str(data.get('os', 'windows')).lower()
            if target_os not in _BINARY_TARGET_OSES:
                await self._send_json(
                    writer,
                    request,
                    '400 Bad Request',
                    {
                        'message': 'Unsupported binary injection target OS.',
                        'notice': 'error',
                        'usb_agent': self._usb_agent_state(),
                    },
                )
                return

            self._execution_stream.reset()
            self._execution_stream.publish('Detect', 'loading')

            if not self._usb_agent_state().get('mounted'):
                self._execution_stream.publish('Detect', 'error', reason='USB drive not mounted')
                await self._send_json(
                    writer,
                    request,
                    '400 Bad Request',
                    {
                        'message': 'Activate the USB injector before typing the stager.',
                        'notice': 'error',
                        'usb_agent': self._usb_agent_state(),
                    },
                )
                return
            if not self._binary_matches_target(target_os):
                target_notice = self._binary_target_notice(target_os)
                self._execution_stream.publish('Detect', 'error', reason=target_notice)
                await self._send_json(
                    writer,
                    request,
                    '400 Bad Request',
                    {
                        'message': target_notice,
                        'notice': 'error',
                        'usb_agent': self._usb_agent_state(),
                    },
                )
                return

            self._execution_stream.publish('Detect', 'success')
            await self._init_execution_loot(target_os)
            self._execution_stream.publish('Copy', 'loading')

            # Fire the HID stager in a background task so this HTTP response
            # can return immediately — the execution SSE stream takes over.
            asyncio.create_task(self._run_binary_injection(target_os))

            await self._send_json(
                writer,
                request,
                '200 OK',
                {
                    'message': 'Injection started.',
                    'notice': 'success',
                    'usb_agent': self._usb_agent_state(),
                },
            )
            return

        if path == '/api/execution/stream' and method == 'GET':
            await self._handle_execution_stream(request, writer)
            return

        await self._send_json(writer, request, '404 Not Found', {'message': 'Not found.'})
