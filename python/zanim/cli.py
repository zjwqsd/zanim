"""Command-line entry points for normal Zanim authoring workflows."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import platform
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .errors import ZanimError
from .runtime import ffmpeg_has_libx264, ffmpeg_path, ffprobe_path
from .scene import Scene
from .source import (
    attach_preview_reload,
    attach_runtime_source,
    capture_runtime_source,
    get_preview_source,
    suppress_preview_calls,
)


def _package_version() -> str:
    try:
        return version("zanim")
    except PackageNotFoundError:
        return "source"


def _module_context(source: Path) -> tuple[str, Path]:
    """Return an importable module name and sys.path root for a scene file."""
    package_parts: list[str] = []
    parent = source.parent
    while (parent / "__init__.py").is_file():
        package_parts.insert(0, parent.name)
        parent = parent.parent
    if package_parts:
        module_name = ".".join((*package_parts, source.stem))
        return module_name, parent
    return f"_zanim_cli_{source.stem}_{abs(hash(str(source))):x}", source.parent


def _load_scene(path: str | Path, builder_name: str | None = None) -> Scene:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ZanimError(f"scene file does not exist: {source}")

    module_name, import_root = _module_context(source)
    root_text = str(import_root)
    if root_text not in sys.path:
        # Match normal script import behavior and keep it for manual reload.
        sys.path.insert(0, root_text)
    package_name = module_name.rpartition(".")[0]
    if package_name:
        importlib.import_module(package_name)

    spec = importlib.util.spec_from_file_location(module_name, source)
    if spec is None or spec.loader is None:
        raise ZanimError(f"cannot load Python scene file: {source}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        # Capture the complete file execution, including a builder call below.
        # This captures runtime object names for bare scripts without decorators.
        with capture_runtime_source(source) as capture:
            # A file may also be directly runnable with `scene.preview()` at its
            # bottom. Under the CLI that call is a no-op; the CLI owns the server.
            with suppress_preview_calls():
                spec.loader.exec_module(module)

            selected_scene: Scene | None = None
            scene_name: str | None = None
            selected_builder: str | None = None

            if builder_name is not None:
                builder = getattr(module, builder_name, None)
                if not callable(builder):
                    raise ZanimError(f"{source.name} does not define callable `{builder_name}()`")
                selected_scene = builder()
                selected_builder = builder_name
            else:
                direct = getattr(module, "scene", None)
                if isinstance(direct, Scene):
                    selected_scene = direct
                    scene_name = "scene"
                else:
                    builder = getattr(module, "build_scene", None)
                    if callable(builder):
                        selected_scene = builder()
                        selected_builder = "build_scene"
                    else:
                        candidates = [
                            (name, value)
                            for name, value in vars(module).items()
                            if isinstance(value, Scene) and not name.startswith("_")
                        ]
                        if len(candidates) == 1:
                            scene_name, selected_scene = candidates[0]
                        elif len(candidates) > 1:
                            names = ", ".join(name for name, _ in candidates)
                            raise ZanimError(
                                f"{source.name} defines multiple Scene globals ({names}); "
                                "name the intended one `scene` or pass --builder"
                            )

        if not isinstance(selected_scene, Scene):
            if builder_name is not None:
                raise ZanimError(
                    f"{builder_name}() must return Scene, got {type(selected_scene).__name__}"
                )
            raise ZanimError(
                f"{source.name} must define `scene = Scene(...)`, exactly one Scene global, "
                "or callable `build_scene()`"
            )

        # A decorated builder may already have local object names. Bare scripts use
        # module globals plus any Scene-builder return locals captured at runtime.
        if get_preview_source(selected_scene) is None:
            attach_runtime_source(
                selected_scene,
                capture,
                vars(module),
                module_name=module_name,
                package_name=package_name,
                builder_name=selected_builder,
            )
        attach_preview_reload(
            selected_scene,
            path=source,
            module_name=module_name,
            package_name=package_name,
            scene_name=scene_name,
            builder_name=selected_builder,
        )
        return selected_scene
    except Exception:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise


# Kept as a private compatibility alias while product code moves to _load_scene.
def _load_builder(path: str | Path, builder_name: str = "build_scene") -> Scene:
    return _load_scene(path, builder_name)


def _cmd_preview(args) -> int:
    scene = _load_scene(args.file, args.builder)
    scene.preview(
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser,
        allow_remote_reload=args.allow_remote_reload,
    )
    return 0


def _cmd_render(args) -> int:
    scene = _load_scene(args.file, args.builder)
    source = Path(args.file).resolve()
    if args.time is not None and (args.start is not None or args.end is not None):
        raise ZanimError("--time cannot be combined with --start/--end")

    if args.output:
        output = Path(args.output)
    elif args.time is not None or scene.duration <= 0:
        output = Path(f"{source.stem}.png")
    else:
        output = Path(f"{source.stem}.mp4")

    result = scene.render(output, time=args.time, start=args.start, end=args.end)
    print(result)
    return 0


def _cmd_export_ir(args) -> int:
    scene = _load_scene(args.file, args.builder)
    from .ir import write_scene_ir

    source = Path(args.file).resolve()
    output = Path(args.output) if args.output else Path(f"{source.stem}.zanim.json")
    result = write_scene_ir(
        scene,
        output,
        sample_transform_functions=args.sample_transform_functions,
        sample_dynamic_providers=args.sample_dynamic_providers,
        sample_fps=args.sample_fps,
    )
    print(result)
    return 0


def _cmd_render_ir(args) -> int:
    from .ir import load_scene_ir

    scene = load_scene_ir(args.file)
    source = Path(args.file).resolve()
    if args.time is not None and (args.start is not None or args.end is not None):
        raise ZanimError("--time cannot be combined with --start/--end")
    if args.output:
        output = Path(args.output)
    elif args.time is not None or scene.duration <= 0:
        output = Path(f"{source.stem}.png")
    else:
        output = Path(f"{source.stem}.mp4")
    result = scene.render(output, time=args.time, start=args.start, end=args.end)
    print(result)
    return 0


def _cmd_info(_args) -> int:
    from .render.abi import native_diagnostics

    native = native_diagnostics()
    ffmpeg = ffmpeg_path()
    try:
        from .typst import _typst_executable

        typst = str(_typst_executable())
    except Exception:
        typst = None
    print(f"Zanim      {_package_version()}")
    print(f"Python     {platform.python_version()}")
    print(f"Platform   {platform.system()} {platform.machine()}")
    print(f"Renderer   {'OK' if native['ok'] else 'ERROR'}")
    print(f"  library  {native['path'] or 'not found'}")
    print(f"  ABI      {native['abi'] if native['abi'] is not None else 'unknown'}")
    if native["error"]:
        print(f"  error    {native['error']}")
    print(f"Typst      {typst or 'not found'}")
    print(f"FFmpeg     {ffmpeg or 'not found'}")
    print(f"FFprobe    {ffprobe_path() or 'not found'}")
    print(f"libx264    {'yes' if ffmpeg_has_libx264() else 'no'}")
    return 0 if native["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zanim", description="Zanim animation tools")
    sub = parser.add_subparsers(dest="command", required=True)

    preview = sub.add_parser("preview", help="open browser-native Scene IR preview")
    preview.add_argument("file", help="Python scene script")
    preview.add_argument("--builder", help="explicit Scene builder function (optional)")
    preview.add_argument("--host", default="127.0.0.1")
    preview.add_argument("--port", type=int, default=8765)
    preview.add_argument("--no-browser", action="store_true")
    preview.add_argument(
        "--allow-remote-reload",
        action="store_true",
        help="allow source-code reload when Preview is exposed beyond loopback",
    )
    preview.set_defaults(func=_cmd_preview)

    render = sub.add_parser("render", help="render a Scene from a Python file")
    render.add_argument("file", help="Python scene script")
    render.add_argument("-o", "--output")
    render.add_argument("--builder", help="explicit Scene builder function (optional)")
    render.add_argument("--time", type=float, help="render one absolute-time image")
    render.add_argument("--start", type=float, help="video interval start time")
    render.add_argument("--end", type=float, help="video interval end time")
    render.set_defaults(func=_cmd_render)

    export_ir = sub.add_parser("export-ir", help="compile a Python Scene to portable Scene IR")
    export_ir.add_argument("file", help="Python scene script")
    export_ir.add_argument("-o", "--output")
    export_ir.add_argument("--builder", help="explicit Scene builder function (optional)")
    export_ir.add_argument(
        "--sample-transform-functions",
        action="store_true",
        help="bake TransformFunctionClip callbacks to frame-rate sampled tracks",
    )
    export_ir.add_argument(
        "--sample-dynamic-providers",
        action="store_true",
        help="bake dynamic geometry/batch/vector providers to frame-rate sampled tracks",
    )
    export_ir.add_argument("--sample-fps", type=int, help="sample rate for baked runtime providers")
    export_ir.set_defaults(func=_cmd_export_ir)

    render_ir = sub.add_parser("render-ir", help="render portable Scene IR with the native backend")
    render_ir.add_argument("file", help="Scene IR JSON file")
    render_ir.add_argument("-o", "--output")
    render_ir.add_argument("--time", type=float, help="render one absolute-time image")
    render_ir.add_argument("--start", type=float, help="video interval start time")
    render_ir.add_argument("--end", type=float, help="video interval end time")
    render_ir.set_defaults(func=_cmd_render_ir)

    info = sub.add_parser("info", help="show runtime and dependency diagnostics")
    info.set_defaults(func=_cmd_info)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ZanimError, ValueError, TypeError) as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
