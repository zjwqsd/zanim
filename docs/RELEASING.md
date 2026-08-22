# Releasing Zanim

Zanim's runtime is Python plus a bundled Zig shared library loaded through `ctypes`. A release is therefore a platform-wheel release, not a source-only Python upload.

## Release gates

Before publishing a public release:

1. Choose and add the project `LICENSE`. Do not publish until this is explicit.
2. Review third-party licenses for z2d, Pillow, Zstandard, Typst integration/assets, and example media/data. FFmpeg is currently a system dependency and is **not** redistributed by the Zanim wheel.
3. CI must pass on Linux and Windows for every supported Python version.
4. Download a CI wheel into a clean machine/VM and run `zanim info` plus `scripts/wheel_smoke.py`.
5. Linux PyPI wheels must receive a standards-compliant manylinux tag after policy verification. Do not upload a generic `linux_x86_64` wheel as the final public artifact.
6. Configure PyPI Trusted Publishing only after the package name/account ownership is settled.

## Local release check

```bash
./scripts/check.sh
uv build --wheel
```

Then install the wheel into a new environment rather than testing from the repository:

```bash
uv venv /tmp/zanim-release-check
uv pip install --python /tmp/zanim-release-check/bin/python dist/*.whl
cd /tmp
/tmp/zanim-release-check/bin/zanim info
```

Expected runtime properties:

- `Renderer OK` and native ABI matches Python's `ABI_VERSION`.
- The renderer path is inside `site-packages/zanim/_native/`, not the source checkout.
- Zig is not needed for preview/render after installation.
- `zanim info` reports Typst, FFmpeg/ffprobe and libx264 availability.
- Missing FFmpeg produces a `MediaError` with installation guidance rather than a raw `FileNotFoundError`.

## Versioning before 1.0

Use SemVer-style pre-1.0 releases:

- patch (`0.x.y`) for compatible fixes;
- minor (`0.x.0`) for meaningful public authoring/API changes;
- `1.0.0` only after the public authoring API and wheel support policy are intentionally stable.
