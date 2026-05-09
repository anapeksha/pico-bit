import gc
import json

from device_config import AP_SSID
from ducky import (
    DEFAULT_PAYLOAD,
    PAYLOAD_FILE,
    analyze_script,
    ensure_payload,
    find_payload,
)
from ducky.analysis import AnalysisResult
from keyboard_layouts import (
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

from ._http import (
    _JSON_HEADERS,
    _KEYBOARD_LAYOUT_FILE,
    _LOOT_FILE,
    _NO_STORE,
    _RUN_HISTORY_LIMIT,
    _merge_headers,
    _ticks_ms,
)


class _PayloadMixin:
    # Attributes provided by SetupServer.__init__
    _ap_ip: str
    _ap_password_in_use: str
    _keyboard_layout: str
    _payload_seeded: bool
    _run_history: list[dict[str, object]]
    _run_sequence: int

    # Methods provided by SetupServer / other mixins
    def _auth_enabled(self) -> bool: ...
    def _is_authorized(self, request) -> bool: ...
    def _keyboard_ready(self) -> bool: ...
    def _has_binary(self) -> bool: ...
    def _stager_script(self, target_os: str) -> str: ...
    async def _send(self, writer, request, status: str, body, headers=None) -> None: ...
    async def _send_json(self, writer, request, status: str, data: dict[str, object]) -> None: ...
    async def _run_payload(self, script: str, *, source: str = 'portal') -> tuple[str, str]: ...

    def _seed_payload(self) -> str:
        payload_path, created = ensure_payload(seed=DEFAULT_PAYLOAD)
        if created:
            self._payload_seeded = True
        return payload_path

    def _read_payload(self) -> str:
        gc.collect()
        payload_path = self._seed_payload()
        try:
            with open(payload_path) as f:
                return f.read()
        except OSError:
            return DEFAULT_PAYLOAD

    def _write_payload(self, content: str) -> str:
        payload_path = find_payload() or PAYLOAD_FILE
        with open(payload_path, 'w') as f:
            f.write(content)
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
        if persist:
            self._persist_keyboard_layout(normalized)
        return normalized

    def _keyboard_layout_state(self) -> dict[str, object]:
        option = layout_option(self._keyboard_layout)
        platform, layout = split_layout_code(self._keyboard_layout)
        target_label = option['platform_label'] + ' · ' + option['label']
        return {
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
        return [dict(item) for item in self._run_history]

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

    def _bootstrap_state(self) -> dict[str, object]:
        message = ''
        notice = 'quiet'
        if self._payload_seeded:
            message = 'payload.dd was seeded on this boot.'
        payload = self._read_payload()

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
            await self._send_json(writer, request, '200 OK', self._bootstrap_state())
            return

        if request['method'] == 'POST' and request['path'] == '/api/payload':
            data = json.loads(request['body'].decode('utf-8', 'ignore') or '{}')
            payload = str(data.get('payload', '')).replace('\r\n', '\n')
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

            self._write_payload(payload)
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
            payload = str(data.get('payload', self._read_payload())).replace('\r\n', '\n')
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
                self._write_payload(payload)
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
            try:
                with open(_LOOT_FILE) as f:
                    content = f.read()
                await self._send(
                    writer,
                    request,
                    '200 OK',
                    content.encode(),
                    headers=_merge_headers(_JSON_HEADERS, _NO_STORE),
                )
            except OSError:
                await self._send_json(
                    writer, request, '404 Not Found', {'message': 'No loot collected yet.'}
                )
            return

        if path == '/api/loot/download' and method == 'GET':
            try:
                with open(_LOOT_FILE) as f:
                    content = f.read()
                await self._send(
                    writer,
                    request,
                    '200 OK',
                    content.encode(),
                    headers=_merge_headers(
                        _JSON_HEADERS,
                        {'Content-Disposition': 'attachment; filename="loot.json"'},
                        _NO_STORE,
                    ),
                )
            except OSError:
                await self._send_json(
                    writer, request, '404 Not Found', {'message': 'No loot collected yet.'}
                )
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
            script = self._stager_script(target_os)
            message, notice = await self._run_payload(script)
            status = '200 OK' if notice == 'success' else '400 Bad Request'
            await self._send_json(
                writer,
                request,
                status,
                {'message': message, 'notice': notice, 'run_history': self._recent_runs()},
            )
            return

        await self._send_json(writer, request, '404 Not Found', {'message': 'Not found.'})
