"""Ensure minimal and legacy Gateway images contain the first-party participant UI."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTICIPANT_APP = ROOT / "apps" / "delphi-participant"


def test_gateway_and_kernel_images_copy_participant_browser_assets():
    expected = "COPY apps/delphi-participant/ ./apps/delphi-participant/"
    for dockerfile_name in ("Dockerfile.gateway", "Dockerfile.kernel"):
        source = (ROOT / dockerfile_name).read_text(encoding="utf-8")
        assert expected in source

    assert (PARTICIPANT_APP / "index.html").is_file()
    assert (PARTICIPANT_APP / "app.js").is_file()
    assert (PARTICIPANT_APP / "styles.css").is_file()


def test_kernel_image_manifest_hashes_all_first_party_delphi_assets():
    manifest_source = (ROOT / "services" / "core" / "image_manifest.py").read_text(
        encoding="utf-8"
    )
    for suffix in ('".html"', '".js"', '".css"'):
        assert suffix in manifest_source
