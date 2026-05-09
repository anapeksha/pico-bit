"""Helpers for tiny Server-Sent Events responses."""


def sse_event(*, event: str, data: str, event_id: int | None = None) -> bytes:
    lines: list[str] = []
    if event_id is not None:
        lines.append(f'id: {event_id}')
    if event:
        lines.append(f'event: {event}')
    for line in (data or '').splitlines() or ['']:
        lines.append(f'data: {line}')
    lines.append('')
    lines.append('')
    return '\n'.join(lines).encode()


def sse_comment(text: str) -> bytes:
    return f': {text}\n\n'.encode()
