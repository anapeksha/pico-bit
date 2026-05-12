from web_assets import STATIC_ASSETS

from ._http import _NO_STORE, _merge_headers

_GZIP_HEADERS = {
    'Content-Encoding': 'gzip',
    'Vary': 'Accept-Encoding',
}

_STATIC_CACHE = {
    'Cache-Control': 'public, max-age=3600',
}


class AppRenderer:
    """Serve compiled SPA assets and render the initial auth-aware shell."""

    def __init__(self, assets=STATIC_ASSETS) -> None:
        self._assets = assets

    def get(self, path: str):
        for route, body, mime_type in self._assets:
            if route == path:
                return body, mime_type
        return None

    def render(self, path: str = '/', replacements=None) -> str:
        asset = self.get(path)
        if not asset:
            return ''
        body, mime_type = asset
        if not mime_type.startswith('text/html'):
            return ''
        page = body.decode()
        for key, value in (replacements or {}).items():
            page = page.replace('{{' + key + '}}', value)
        return page

    def render_shell(
        self,
        *,
        auth_state: str = 'portal',
        message_class: str = 'notice--hidden',
        message: str = '',
        username: str = '',
    ) -> str:
        return self.render(
            '/',
            {
                'auth_state': auth_state,
                'message_class': message_class,
                'message': message,
                'username': username,
            },
        )

    async def send_static(self, owner, writer, request) -> bool:
        asset = self.get(request['path'])
        if not asset:
            return False
        body, mime_type = asset
        headers = {'Content-Type': mime_type}
        if mime_type.startswith('text/html'):
            headers = _merge_headers(headers, _NO_STORE)
        else:
            headers = _merge_headers(headers, _GZIP_HEADERS, _STATIC_CACHE)

        await owner._send(
            writer,
            request,
            '200 OK',
            body,
            headers=headers,
        )
        return True

    async def send_shell(
        self,
        owner,
        writer,
        request,
        *,
        auth_state: str,
        message_class: str = 'notice--hidden',
        message: str = '',
        username: str = '',
    ) -> None:
        await owner._send(
            writer,
            request,
            '200 OK',
            self.render_shell(
                auth_state=auth_state,
                message_class=message_class,
                message=message,
                username=username,
            ),
            headers=_merge_headers({'Content-Type': 'text/html; charset=utf-8'}, _NO_STORE),
        )
