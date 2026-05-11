import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ASSET_PIPELINE = importlib.import_module('scripts.asset_pipeline')

WEB_ASSET_SIZE_BUDGET = 70_235
WEB_ASSET_EXPORTS = (
    'INDEX_HTML',
    'INDEX_CSS',
    'INDEX_JS',
    'LOGIN_HTML',
    'PORTAL_CSS',
    'PORTAL_JS',
)
WEB_UNIQUE_ASSET_EXPORTS = ('INDEX_HTML', 'INDEX_CSS', 'INDEX_JS')


def test_render_web_assets_contains_expected_exports() -> None:
    ASSET_PIPELINE.build_frontend()
    rendered = ASSET_PIPELINE.render_web_assets()

    for name in WEB_ASSET_EXPORTS:
        assert f'{name}: bytes =' in rendered


def test_embedded_web_assets_are_in_sync() -> None:
    ASSET_PIPELINE.sync_web_assets(check=True)


def test_embedded_web_assets_stay_within_raw_byte_budget() -> None:
    ASSET_PIPELINE.build_frontend()
    namespace: dict[str, object] = {}
    exec(ASSET_PIPELINE.render_web_assets(), namespace)

    total = 0
    for name in WEB_UNIQUE_ASSET_EXPORTS:
        value = namespace[name]
        assert isinstance(value, bytes)
        total += len(value)

    assert total <= WEB_ASSET_SIZE_BUDGET
