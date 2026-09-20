# Releasing Zanim

Zanim is intentionally pre-1.0. Python and Web use independent version streams.

Current release candidates:

- Python: `zanim 0.7.0rc1`
- Web: `@zanim/web 0.1.0-beta.1`

## One-time registry setup

### PyPI

Create/claim the `zanim` project and configure a PyPI Trusted Publisher for the GitHub repository, the `CI` workflow, and the `pypi` environment. The workflow publishes only tags beginning with `v`.

### npm

Create/claim the `@zanim` scope and allow public scoped packages. Add an `NPM_TOKEN` repository secret for the first publish, or migrate the `Publish Web` workflow to npm Trusted Publishing after the package exists.

## Python preflight

```bash
uv sync --frozen
./scripts/check.sh
uv build --wheel
mkdir -p repaired
uvx auditwheel repair dist/zanim-*.whl --wheel-dir repaired  # Linux only
```

Install the built/repaired wheel into a clean environment and run:

```bash
zanim --version
zanim info
python scripts/wheel_smoke.py
```

The GitHub CI repeats this on Python 3.12/3.13 across Linux, Windows, and macOS. Linux wheels are repaired to manylinux before upload.

Publish by pushing a tag that exactly matches `pyproject.toml`, for example:

```bash
git tag v0.7.0rc1
git push origin v0.7.0rc1
```

## Web preflight

```bash
cd web
npm ci
./build.sh
npm test
npm pack --dry-run
```

A real tarball should contain the JS sources/types, WASM runtime, README, CHANGELOG, and LICENSE, with no preview/test/node_modules files.

Publish with an independent Web tag matching `web/package.json`:

```bash
git tag web-v0.1.0-beta.1
git push origin web-v0.1.0-beta.1
```

The `Publish Web` workflow validates the tag/package version before `npm publish --provenance`. Prerelease versions such as `0.1.0-beta.1` use the npm `beta` dist-tag; non-prerelease 0.x versions use `latest`.
