from __future__ import annotations

import ast
import functools
import importlib.util
import inspect
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar, cast

from .bound import BoundItem
from .scene import Scene
from .timeline import Timeline

F = TypeVar("F", bound=Callable[..., Scene])


@dataclass(frozen=True, slots=True)
class SourceSpan:
    path: str
    start_line: int
    end_line: int

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }


@dataclass(frozen=True, slots=True)
class PreviewSourceInfo:
    path: str
    text: str
    module_name: str
    package_name: str
    builder_name: str | None
    object_names: dict[int, tuple[str, ...]]
    clip_sources: dict[int, SourceSpan]

    def primary_name(self, object_id: int) -> str | None:
        names = self.object_names.get(int(object_id), ())
        return names[0] if names else None

    def clip_source(self, clip) -> SourceSpan | None:
        return self.clip_sources.get(id(clip))


@dataclass(frozen=True, slots=True)
class PreviewReloadInfo:
    path: str
    module_name: str
    package_name: str
    scene_name: str | None = None
    builder_name: str | None = None


_SUPPRESS_PREVIEW = ContextVar("zanim_suppress_preview", default=False)


@contextmanager
def suppress_preview_calls():
    token = _SUPPRESS_PREVIEW.set(True)
    try:
        yield
    finally:
        _SUPPRESS_PREVIEW.reset(token)


def preview_calls_suppressed() -> bool:
    return bool(_SUPPRESS_PREVIEW.get())


def get_preview_source(scene: Scene) -> PreviewSourceInfo | None:
    value = scene._preview_source_info
    return value if isinstance(value, PreviewSourceInfo) else None


def get_preview_reload(scene: Scene) -> PreviewReloadInfo | None:
    value = scene._preview_reload_info
    return value if isinstance(value, PreviewReloadInfo) else None


def attach_preview_reload(
    scene: Scene,
    *,
    path: str | Path,
    module_name: str,
    package_name: str = "",
    scene_name: str | None = None,
    builder_name: str | None = None,
) -> Scene:
    if (scene_name is None) == (builder_name is None):
        raise ValueError("preview reload needs exactly one of scene_name or builder_name")
    scene._preview_reload_info = PreviewReloadInfo(
        path=str(Path(path).resolve()),
        module_name=str(module_name),
        package_name=str(package_name or ""),
        scene_name=scene_name,
        builder_name=builder_name,
    )
    return scene


def infer_script_reload(scene: Scene, frame) -> None:
    """Attach reload metadata for a top-level ``scene.preview()`` script."""
    if get_preview_reload(scene) is not None or frame is None:
        return
    if frame.f_code.co_name != "<module>":
        return
    path_value = frame.f_globals.get("__file__")
    if not path_value:
        return
    path = Path(path_value).resolve()
    if not path.is_file():
        return
    candidates = [
        name
        for name, value in frame.f_globals.items()
        if value is scene and not name.startswith("__")
    ]
    if not candidates:
        return
    scene_name = "scene" if "scene" in candidates else candidates[0]
    module_name = str(frame.f_globals.get("__name__") or path.stem)
    package_name = str(frame.f_globals.get("__package__") or "")
    # Direct ``python demo.py`` starts Preview after the earlier clips have
    # already been authored, so their call sites cannot be recovered reliably.
    # Global object names are still exact and useful; ``zanim preview demo.py``
    # captures both names and clip call sites from the start of execution.
    if get_preview_source(scene) is None:
        source = _SourceFile(path)
        scene._preview_source_info = PreviewSourceInfo(
            path=str(source.path),
            text=source.text,
            module_name=module_name,
            package_name=package_name,
            builder_name=None,
            object_names=_object_names(scene, frame.f_globals),
            clip_sources={},
        )
    attach_preview_reload(
        scene,
        path=path,
        module_name=module_name,
        package_name=package_name,
        scene_name=scene_name,
    )


class _SourceFile:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.text = self.path.read_text(encoding="utf-8")
        tree = ast.parse(self.text, filename=str(self.path))
        self._calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(node, "lineno", None) is not None
            and getattr(node, "end_lineno", None) is not None
        ]

    def call_span(self, line: int) -> SourceSpan:
        matches = [node for node in self._calls if node.lineno <= line <= node.end_lineno]
        if matches:
            node = min(
                matches, key=lambda value: (value.end_lineno - value.lineno, value.col_offset)
            )
            return SourceSpan(str(self.path), int(node.lineno), int(node.end_lineno))
        return SourceSpan(str(self.path), int(line), int(line))


def _source_frame(frame, path: Path):
    target = str(path)
    while frame is not None:
        try:
            current = str(Path(frame.f_code.co_filename).resolve())
        except OSError:
            current = frame.f_code.co_filename
        if current == target:
            return frame
        frame = frame.f_back
    return None


def _object_names(scene: Scene, locals_at_return: dict[str, object]) -> dict[int, tuple[str, ...]]:
    names: dict[int, list[str]] = {}
    by_identity = {id(item.object_ref): item.object_id for item in scene._registry}
    for name, value in locals_at_return.items():
        raw = value.raw if isinstance(value, BoundItem) else value
        object_id = by_identity.get(id(raw))
        if object_id is None:
            continue
        entries = names.setdefault(object_id, [])
        if name not in entries:
            entries.append(name)
    return {object_id: tuple(entries) for object_id, entries in names.items()}


@dataclass(slots=True)
class _RuntimeSourceCapture:
    source: _SourceFile
    clip_sources: dict[int, SourceSpan]


@contextmanager
def capture_runtime_source(path: str | Path):
    """Capture Timeline clip call sites while one Python source file executes.

    This is the source-aware path used by ``zanim preview file.py``. It observes
    the real runtime call stack, so loops, helpers and parallel blocks do not
    need AST heuristics or special authoring syntax.
    """
    source = _SourceFile(Path(path))
    capture = _RuntimeSourceCapture(source, {})
    append_code = Timeline._append.__code__
    previous = sys.getprofile()

    def profiler(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event != "call" or frame.f_code is not append_code:
            return
        clip = frame.f_locals.get("clip")
        caller = _source_frame(frame.f_back, source.path)
        if clip is not None and caller is not None:
            capture.clip_sources[id(clip)] = source.call_span(caller.f_lineno)

    sys.setprofile(profiler)
    try:
        yield capture
    finally:
        sys.setprofile(previous)


def attach_runtime_source(
    scene: Scene,
    capture: _RuntimeSourceCapture,
    namespace: dict[str, object],
    *,
    module_name: str,
    package_name: str = "",
    builder_name: str | None = None,
) -> Scene:
    """Attach names/source spans captured while executing a scene module."""
    scene._preview_source_info = PreviewSourceInfo(
        path=str(capture.source.path),
        text=capture.source.text,
        module_name=str(module_name),
        package_name=str(package_name or ""),
        builder_name=builder_name,
        object_names=_object_names(scene, namespace),
        clip_sources=dict(capture.clip_sources),
    )
    return scene


def preview_source(func: F) -> F:
    """Attach runtime-to-source metadata to a Scene builder for Preview tooling.

    The wrapped function still returns the original Scene. During that one call
    we observe Timeline clip creation and the builder's return locals; Scene,
    Timeline and renderer data structures remain unchanged.
    """
    path_value = inspect.getsourcefile(func) or inspect.getfile(func)
    source = _SourceFile(Path(path_value))
    append_code = Timeline._append.__code__

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        clip_sources: dict[int, SourceSpan] = {}
        return_locals: dict[str, object] = {}
        previous = sys.getprofile()

        def profiler(frame, event, arg):
            if previous is not None:
                previous(frame, event, arg)
            if event == "call" and frame.f_code is append_code:
                clip = frame.f_locals.get("clip")
                caller = _source_frame(frame.f_back, source.path)
                if clip is not None and caller is not None:
                    clip_sources[id(clip)] = source.call_span(caller.f_lineno)
            elif event == "return" and frame.f_code is func.__code__:
                return_locals.update(frame.f_locals)

        sys.setprofile(profiler)
        try:
            scene = func(*args, **kwargs)
        finally:
            sys.setprofile(previous)

        if not isinstance(scene, Scene):
            raise TypeError("@preview_source function must return Scene")
        package_name = str(func.__globals__.get("__package__") or "")
        scene._preview_source_info = PreviewSourceInfo(
            path=str(source.path),
            text=source.text,
            module_name=func.__module__,
            package_name=package_name,
            builder_name=func.__name__,
            object_names=_object_names(scene, return_locals),
            clip_sources=clip_sources,
        )
        attach_preview_reload(
            scene,
            path=source.path,
            module_name=func.__module__,
            package_name=package_name,
            builder_name=func.__name__,
        )
        return scene

    return cast(F, wrapped)


def _resolve_reloaded_scene(module, info: PreviewReloadInfo) -> Scene:
    if info.builder_name is not None:
        builder = getattr(module, info.builder_name, None)
        if not callable(builder):
            raise RuntimeError(f"reload source no longer defines {info.builder_name}()")
        scene = builder()
    else:
        assert info.scene_name is not None
        scene = getattr(module, info.scene_name, None)
    if not isinstance(scene, Scene):
        target = f"{info.builder_name}()" if info.builder_name else info.scene_name
        raise TypeError(f"reload target {target} must produce Scene")
    return scene


def reload_preview_scene(scene: Scene) -> Scene:
    """Re-execute the file backing a Preview scene in an isolated module."""
    info = get_preview_reload(scene)
    if info is None:
        raise RuntimeError(
            "manual reload requires either a source-aware builder or a directly loaded scene script"
        )
    path = Path(info.path).resolve()
    text = path.read_text(encoding="utf-8")
    code = compile(text, str(path), "exec")
    private_name = f"_zanim_preview_reload_{abs(hash(str(path))):x}"
    module_name = f"{info.package_name}.{private_name}" if info.package_name else private_name
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot create module spec for {path}")

    previous = sys.modules.get(module_name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        # A directly executable scene may end in scene.preview(). During a
        # manual rebuild that call is intentionally a no-op: the existing server
        # owns the browser/session and only needs the newly authored Scene.
        with capture_runtime_source(path) as capture:
            with suppress_preview_calls():
                exec(code, module.__dict__)
            new_scene = _resolve_reloaded_scene(module, info)
        # Decorated builders attach richer local-variable metadata themselves.
        # Bare scripts and undecorated builders receive the runtime module map.
        if get_preview_source(new_scene) is None:
            attach_runtime_source(
                new_scene,
                capture,
                module.__dict__,
                module_name=info.module_name,
                package_name=info.package_name,
                builder_name=info.builder_name,
            )
        attach_preview_reload(
            new_scene,
            path=path,
            module_name=info.module_name,
            package_name=info.package_name,
            scene_name=info.scene_name,
            builder_name=info.builder_name,
        )
        return new_scene
    except BaseException:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise


# Backward-compatible internal name used by existing tests/callers.
def reload_preview_source(scene: Scene) -> Scene:
    return reload_preview_scene(scene)
