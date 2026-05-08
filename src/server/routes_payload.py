import json

from keyboard_layouts import (
    compose_layout_code,
    default_layout_code,
    is_supported_layout,
    is_supported_platform,
    layout_option,
    normalize_platform_code,
    split_layout_code,
)
from status_led import STATUS_LED


async def api_bootstrap(portal, request):
    return portal._json_response(portal._bootstrap_state())


async def api_payload(portal, request):
    data = json.loads((request.body or b'').decode('utf-8', 'ignore') or '{}')
    payload = str(data.get('payload', '')).replace('\r\n', '\n')
    validation = portal._validation_state(payload)
    if validation['blocking']:
        return portal._json_response(
            {'message': validation['summary'], 'notice': 'error', 'validation': validation},
            400,
        )
    portal._write_payload(payload)
    return portal._json_response(
        {'message': 'payload.dd saved.', 'notice': 'success', 'validation': validation}
    )


async def api_validate(portal, request):
    data = json.loads((request.body or b'').decode('utf-8', 'ignore') or '{}')
    payload = str(data.get('payload', '')).replace('\r\n', '\n')
    validation = portal._validation_state(payload)
    return portal._json_response(
        {
            'message': validation['summary'],
            'notice': validation['notice'],
            'validation': validation,
        }
    )


async def api_keyboard_layout(portal, request):
    data = json.loads((request.body or b'').decode('utf-8', 'ignore') or '{}')
    requested_os = data.get('os')
    requested_layout = data.get('layout')
    current_os, _current_layout = split_layout_code(portal._keyboard_layout)

    if requested_os is not None and not is_supported_platform(str(requested_os)):
        result = {
            'message': 'Unsupported operating system.',
            'notice': 'error',
        }
        result.update(portal._keyboard_layout_state())
        return portal._json_response(result, 400)

    platform = normalize_platform_code(str(requested_os or current_os))
    layout_text = str(requested_layout or '').strip()
    if layout_text:
        normalized = compose_layout_code(platform, layout_text)
        if not is_supported_layout(normalized):
            platform_label = layout_option(default_layout_code(platform))['platform_label']
            result = {
                'message': f'Unsupported keyboard layout for {platform_label}.',
                'notice': 'error',
            }
            result.update(portal._keyboard_layout_state())
            return portal._json_response(result, 400)
    else:
        normalized = default_layout_code(platform)

    portal._set_keyboard_layout(normalized, persist=True)
    await STATUS_LED.show('keyboard_layout_changed')
    option = layout_option(normalized)
    result = {
        'message': f'Typing target set to {option["platform_label"]} · {option["label"]}.',
        'notice': 'success',
    }
    result.update(portal._keyboard_layout_state())
    return portal._json_response(result)


async def api_run(portal, request):
    data = json.loads((request.body or b'').decode('utf-8', 'ignore') or '{}')
    payload = str(data.get('payload', portal._read_payload())).replace('\r\n', '\n')
    validation = portal._validation_state(payload)
    if validation['blocking']:
        return portal._json_response(
            {'message': validation['summary'], 'notice': 'error', 'validation': validation},
            400,
        )
    if data.get('save', True):
        portal._write_payload(payload)
    message, notice = await portal._run_payload(payload)
    status = 200 if notice == 'success' else 400
    return portal._json_response(
        {
            'message': message,
            'notice': notice,
            'run_history': portal._recent_runs(),
            'validation': validation,
        },
        status,
    )
