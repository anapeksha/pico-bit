from microdot.microdot import Response

from web_assets import INDEX_HTML


async def handle_logout(portal, request):
    portal._clear_session(request)
    return Response(
        b'',
        303,
        headers={  # type: ignore[arg-type]
            'Location': '/login',
            'Set-Cookie': [portal._expired_session_cookie()],
            'Cache-Control': 'no-store',
        },
    )


async def handle_index(portal, request):
    if not portal._is_authorized(request):
        return Response(b'', 303, headers={'Location': '/login'})
    return Response(
        INDEX_HTML,
        200,
        headers={
            'Content-Type': 'text/html; charset=utf-8',
            'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff',
        },
    )
