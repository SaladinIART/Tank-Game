"""
tests/test_deploy.py
--------------------
Verifies that the Pygbag build artifacts exist and are well-formed.

Run AFTER `python -m pygbag --build --disable-sound-format-error .`
(or `python tools/build_itch.py`).  Skipped automatically when the
build has not been run yet so normal CI test runs don't fail.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

BUILD_WEB = Path("build/web")


# ---------------------------------------------------------------------------
# Skip entire module if build hasn't been run yet
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not BUILD_WEB.exists(),
    reason="build/web/ not found -- run `python -m pygbag --build --disable-sound-format-error .` first",
)


# ---------------------------------------------------------------------------
# Artifact presence
# ---------------------------------------------------------------------------

class TestBuildArtifacts:
    def test_index_html_exists(self):
        assert (BUILD_WEB / "index.html").is_file()

    def test_apk_exists(self):
        apks = list(BUILD_WEB.glob("*.apk"))
        assert apks, "No .apk bundle found in build/web/"

    def test_tar_gz_exists(self):
        tgzs = list(BUILD_WEB.glob("*.tar.gz"))
        assert tgzs, "No .tar.gz archive found in build/web/"

    def test_favicon_exists(self):
        assert (BUILD_WEB / "favicon.png").is_file()


# ---------------------------------------------------------------------------
# index.html sanity
# ---------------------------------------------------------------------------

class TestIndexHtml:
    def test_contains_pygbag_script(self):
        html = (BUILD_WEB / "index.html").read_text(encoding="utf-8", errors="replace")
        # Pygbag injects a <script> that bootstraps the WASM runtime
        assert "<script" in html.lower()

    def test_references_apk(self):
        html = (BUILD_WEB / "index.html").read_text(encoding="utf-8", errors="replace")
        assert ".apk" in html

    def test_no_localhost_hardcoded(self):
        """Build artifact must not hard-code localhost (would break itch.io/GH Pages)."""
        html = (BUILD_WEB / "index.html").read_text(encoding="utf-8", errors="replace")
        assert "localhost" not in html.lower()


# ---------------------------------------------------------------------------
# APK bundle sanity (it's a zip file)
# ---------------------------------------------------------------------------

class TestApkBundle:
    def _apk_path(self) -> Path:
        return next(BUILD_WEB.glob("*.apk"))

    def test_apk_is_valid_zip(self):
        apk = self._apk_path()
        assert zipfile.is_zipfile(str(apk)), f"{apk.name} is not a valid zip"

    def test_apk_contains_main_py(self):
        apk = self._apk_path()
        with zipfile.ZipFile(str(apk)) as zf:
            names = zf.namelist()
        assert any("main.py" in n for n in names), f"main.py not in apk ({names[:10]}...)"

    def test_apk_contains_data_json(self):
        apk = self._apk_path()
        with zipfile.ZipFile(str(apk)) as zf:
            names = zf.namelist()
        json_files = [n for n in names if n.endswith(".json")]
        assert json_files, "No JSON data files found in apk"

    def test_apk_contains_scenario_m1(self):
        apk = self._apk_path()
        with zipfile.ZipFile(str(apk)) as zf:
            names = zf.namelist()
        assert any("m1.json" in n for n in names), "m1.json scenario not bundled"

    def test_apk_size_reasonable(self):
        """Bundle should be > 50 KB (has content) and < 50 MB (not bloated)."""
        apk = self._apk_path()
        size_mb = apk.stat().st_size / 1_048_576
        assert size_mb > 0.05, f"APK suspiciously small: {size_mb:.2f} MB"
        assert size_mb < 50, f"APK suspiciously large: {size_mb:.2f} MB"


# ---------------------------------------------------------------------------
# itch.io packaging
# ---------------------------------------------------------------------------

class TestItchPackaging:
    def test_build_itch_script_exists(self):
        assert Path("tools/build_itch.py").is_file()

    def test_github_workflow_exists(self):
        assert Path(".github/workflows/deploy.yml").is_file()

    def test_github_workflow_references_pages(self):
        yml = Path(".github/workflows/deploy.yml").read_text()
        assert "deploy-pages" in yml
        assert "upload-pages-artifact" in yml
