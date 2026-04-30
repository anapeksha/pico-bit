import server


def test_page_renders_editor_shell(monkeypatch) -> None:
    monkeypatch.setattr(server, '_read_payload', lambda: 'REM test\nSTRING hi\n')

    html = server._page('Saved', 'success')

    assert 'class="editor__chrome"' in html
    assert 'class="editor__input"' in html
    assert 'payload.dd' in html
    assert server.AP_SSID in html
    assert 'Saved' in html
