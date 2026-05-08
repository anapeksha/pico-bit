from web_assets import INDEX_HTML

from .micro_server import Response


async def handle_logout(portal, request):
    portal.auth.logout(request)
    return Response(
        b'',
        303,
        headers={  # type: ignore[arg-type]
            'Location': '/login',
            'Set-Cookie': [portal.auth.expired_cookie()],
            'Cache-Control': 'no-store',
        },
    )


async def handle_index(portal, request):
    return Response(
        INDEX_HTML,
        200,
        headers={
            'Content-Type': 'text/html; charset=utf-8',
            'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff',
        },
    )
