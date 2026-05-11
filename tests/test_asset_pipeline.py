import importlib
import sys
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ASSET_PIPELINE = importlib.import_module('scripts.asset_pipeline')

WEB_ASSET_SIZE_BUDGET = 150_000
WEB_ASSET_EXPORTS = (
    'INDEX_HTML',
    'INDEX_CSS',
    'INDEX_JS',
    'LOGIN_HTML',
    'PORTAL_CSS',
    'PORTAL_JS',
    'STATIC_ASSET_NAMES',
    'STATIC_ASSETS',
)


def test_render_web_assets_contains_expected_exports() -> None:
    ASSET_PIPELINE.build_frontend()
    rendered = ASSET_PIPELINE.render_web_assets()

    for name in WEB_ASSET_EXPORTS:
        assert name in rendered


def test_embedded_web_assets_are_in_sync() -> None:
    ASSET_PIPELINE.sync_web_assets(check=True)


def test_embedded_web_assets_stay_within_raw_byte_budget() -> None:
    ASSET_PIPELINE.build_frontend()
    namespace: dict[str, object] = {}
    exec(ASSET_PIPELINE.render_web_assets(), namespace)

    total = 0
    for name in cast(tuple[str, ...], namespace['STATIC_ASSET_NAMES']):
        value = namespace[name]
        assert isinstance(value, bytes)
        total += len(value)

    assert total <= WEB_ASSET_SIZE_BUDGET


def test_static_asset_routes_include_mime_types_and_spa_aliases() -> None:
    ASSET_PIPELINE.build_frontend()
    namespace: dict[str, object] = {}
    exec(ASSET_PIPELINE.render_web_assets(), namespace)

    assets = cast(tuple[tuple[str, bytes, str], ...], namespace['STATIC_ASSETS'])
    routes = {route: (body, mime_type) for route, body, mime_type in assets}

    assert routes['/'][1] == 'text/html; charset=utf-8'
    assert routes['/index.html'][0] is routes['/'][0]
    assert routes['/assets/index.css'][1] == 'text/css; charset=utf-8'
    assert routes['/index.css'][0] is routes['/assets/index.css'][0]
    assert routes['/assets/index.js'][1] == 'application/javascript; charset=utf-8'
    assert routes['/index.js'][0] is routes['/assets/index.js'][0]
