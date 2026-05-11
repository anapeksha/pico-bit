from web_assets import STATIC_ASSETS

from ._http import _NO_STORE, _merge_headers


class StaticFileServer:
    def __init__(self, assets=STATIC_ASSETS) -> None:
        self._assets = assets

    def get(self, path: str):
        for route, body, mime_type in self._assets:
            if route == path:
                return body, mime_type
        return None

    def render(self, path: str, replacements: dict[str, str]) -> str:
        asset = self.get(path)
        if not asset:
            return ''
        body, mime_type = asset
        if not mime_type.startswith('text/html'):
            return ''
        page = body.decode()
        for key, value in replacements.items():
            page = page.replace('{{' + key + '}}', value)
        return page

    async def send(self, owner, writer, request) -> bool:
        asset = self.get(request['path'])
        if not asset:
            return False
        body, mime_type = asset
        await owner._send(
            writer,
            request,
            '200 OK',
            body,
            headers=_merge_headers({'Content-Type': mime_type}, _NO_STORE),
        )
        return True
