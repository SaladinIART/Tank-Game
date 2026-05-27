# Deployment

Two targets, one build pipeline.

## Local build

```bash
python -m pygbag --build --disable-sound-format-error .
# -> build/web/ contains: index.html, *.apk (WASM bundle), *.tar.gz, favicon.png
```

## Serve locally

```bash
python -m pygbag .
# Opens http://localhost:8000 in your default browser
```

## GitHub Pages

`.github/workflows/deploy.yml` runs on push to `main`:

1. Install pygame-ce + pygbag + pytest
2. Run the test suite (`pytest tests/`)
3. Regenerate sprites + sounds (`tools/gen_*`)
4. Pygbag build
5. Deploy `build/web/` to Pages via `actions/deploy-pages@v4`

**First-time setup**: Repo Settings → Pages → Source: "GitHub Actions".
Site URL is reported as the workflow output.

## itch.io

```bash
python tools/build_itch.py
# -> dist/itch.zip (~3 MB)
```

Then on itch.io:

1. Create new project → kind: HTML
2. Upload `dist/itch.zip`, tick "This file will be played in the browser"
3. Launch file: `index.html`
4. Embed size: 960×640 (or larger); enable fullscreen button
5. Publish

`--skip-build` flag reuses an existing `build/web/` directory if you just
want to repackage.

## Common pitfalls

- **Pygbag UnicodeDecodeError**: Python source on Windows defaults to
  cp1252 when Pygbag reads it. All source files in this repo are ASCII
  only; if you add Unicode characters (em-dash, arrows, bullets) they'll
  crash the build. Stick to ASCII in `.py` files.
- **WAV warning**: Pygbag prefers OGG. We pass `--disable-sound-format-error`
  because SDL2 in WASM plays WAV fine; convert to OGG only if you hit
  browser compatibility issues in production.
- **Asset paths**: `Path("assets/...")` works in both desktop and the
  WASM virtual filesystem because Pygbag bundles `assets/` into the `.apk`.
  Don't use absolute paths.
- **Browser cache**: hard-refresh (Ctrl+Shift+R) after a redeploy.
