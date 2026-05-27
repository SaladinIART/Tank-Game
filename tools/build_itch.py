"""
tools/build_itch.py
-------------------
Builds the Pygbag WASM bundle and packages it as an itch.io-ready zip.

Usage:
    python tools/build_itch.py [--out dist/itch.zip]

The zip contains everything from build/web/ and can be uploaded to itch.io as
an HTML game with "This file will be played in the browser" checked and
index.html set as the launch file.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD_WEB = ROOT / "build" / "web"
DEFAULT_OUT = ROOT / "dist" / "itch.zip"


def build_pygbag() -> None:
    print("-- Building with Pygbag...")
    result = subprocess.run(
        [sys.executable, "-m", "pygbag", "--build", "--disable-sound-format-error", str(ROOT)],
        cwd=ROOT,
    )
    if result.returncode != 0:
        sys.exit(f"Pygbag build failed (exit {result.returncode})")
    print(f"   build/web/ ready")


def package_zip(out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"-- Packaging {out_path} ...")
    files = list(BUILD_WEB.iterdir())
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, f.name)
            print(f"   + {f.name}  ({f.stat().st_size // 1024} KB)")
    total_kb = out_path.stat().st_size // 1024
    print(f"   => {out_path}  ({total_kb} KB total)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Build itch.io zip")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--skip-build", action="store_true", help="Reuse existing build/web/")
    args = ap.parse_args()

    if not args.skip_build:
        build_pygbag()
    elif not BUILD_WEB.exists():
        sys.exit("build/web/ not found; run without --skip-build first")

    package_zip(Path(args.out))
    print()
    print("itch.io upload checklist:")
    print("  1. Go to https://itch.io/game/new")
    print("  2. Kind of project: HTML")
    print("  3. Upload the zip, tick 'This file will be played in the browser'")
    print("  4. Set launch options: index.html")
    print("  5. Embed options: 960 x 640 (or larger); enable fullscreen button")
    print("  6. Publish!")


if __name__ == "__main__":
    main()
