from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = spec_from_file_location('asset_pipeline', ROOT / 'asset_pipeline.py')
assert SPEC is not None and SPEC.loader is not None
ASSET_PIPELINE = module_from_spec(SPEC)
SPEC.loader.exec_module(ASSET_PIPELINE)


def test_render_web_assets_contains_expected_exports() -> None:
    rendered = ASSET_PIPELINE.render_web_assets()

    assert 'LOGIN_HTML =' in rendered
    assert 'INDEX_HTML =' in rendered
    assert 'PORTAL_CSS =' in rendered
    assert 'PORTAL_JS =' in rendered


def test_embedded_web_assets_are_in_sync() -> None:
    ASSET_PIPELINE.sync_web_assets(check=True)
