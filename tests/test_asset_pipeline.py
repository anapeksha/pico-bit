import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ASSET_PIPELINE = importlib.import_module('scripts.asset_pipeline')


def test_render_web_assets_contains_expected_exports() -> None:
    rendered = ASSET_PIPELINE.render_web_assets()

    assert 'LOGIN_HTML: bytes =' in rendered
    assert 'INDEX_HTML: bytes =' in rendered
    assert 'PORTAL_CSS: bytes =' in rendered
    assert 'PORTAL_JS: bytes =' in rendered


def test_embedded_web_assets_are_in_sync() -> None:
    ASSET_PIPELINE.sync_web_assets(check=True)
