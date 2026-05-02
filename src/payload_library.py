"""Helpers for baked payload-library templates."""

PayloadEntry = tuple[str, str, str, str, bool, str]

PAYLOAD_LIBRARY: tuple[PayloadEntry, ...] = ()


def payload_library_groups(allow_unsafe: bool) -> list[dict[str, object]]:
    groups: dict[str, dict[str, object]] = {}
    order: list[str] = []

    for payload_id, group_key, group_label, label, safe, _script in PAYLOAD_LIBRARY:
        if not allow_unsafe and not safe:
            continue

        group = groups.get(group_key)
        if group is None:
            group = {'key': group_key, 'label': group_label, 'items': []}
            groups[group_key] = group
            order.append(group_key)

        items = group['items']
        items.append({'id': payload_id, 'label': label, 'safe': safe})

    return [groups[key] for key in order]


def payload_library_script(payload_id: str, allow_unsafe: bool) -> str | None:
    for current_id, _group_key, _group_label, _label, safe, script in PAYLOAD_LIBRARY:
        if current_id != payload_id:
            continue
        if not allow_unsafe and not safe:
            return None
        return script
    return None
