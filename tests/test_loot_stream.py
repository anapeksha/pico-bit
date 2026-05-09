from server.loot_stream import LootStreamState
from server.sse import sse_comment, sse_event


def test_loot_stream_publish_advances_revision_and_rotates_waiter() -> None:
    stream = LootStreamState()
    waiter = stream.waiter()

    revision = stream.publish('{"timestamp":1}')

    assert revision == 1
    assert waiter.is_set() is True
    assert stream.waiter() is not waiter
    assert stream.snapshot() == (1, '{"timestamp":1}')


def test_sse_helpers_format_events_and_comments() -> None:
    event = sse_event(event='loot', data='{"timestamp":1}', event_id=7)
    comment = sse_comment('keepalive')

    assert event == b'id: 7\nevent: loot\ndata: {"timestamp":1}\n\n'
    assert comment == b': keepalive\n\n'
