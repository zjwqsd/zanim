from __future__ import annotations

import ast
import functools
import importlib.util
import inspect
import sys
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
    builder_name: str
    object_names: dict[int, tuple[str, ...]]
    clip_sources: dict[int, SourceSpan]

    def primary_name(self, object_id: int) -> str | None:
        names = self.object_names.get(int(object_id), ())
        return names[0] if names else None

    def clip_source(self, clip) -> SourceSpan | None:
        return self.clip_sources.get(id(clip))


def get_preview_source(scene: Scene) -> PreviewSourceInfo | None:
    value = scene._preview_source_info
    return value if isinstance(value, PreviewSourceInfo) else None


class _SourceFile:
    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.text = self.path.read_text(encoding="utf-8")
        tree = ast.parse(self.text, filename=str(self.path))
        self._calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(node, "lineno", None) is not None
            and getattr(node, "end_lineno", None) is not None
        ]

    def call_span(self, line: int) -> SourceSpan:
        matches = [
            node for node in self._calls
            if node.lineno <= line <= node.end_lineno
        ]
        if matches:
            node = min(matches, key=lambda value: (value.end_lineno - value.lineno, value.col_offset))
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
        scene._preview_source_info = PreviewSourceInfo(
            path=str(source.path),
            text=source.text,
            module_name=func.__module__,
            package_name=str(func.__globals__.get("__package__") or ""),
            builder_name=func.__name__,
            object_names=_object_names(scene, return_locals),
            clip_sources=clip_sources,
        )
        return scene

    return cast(F, wrapped)


def reload_preview_source(scene: Scene) -> Scene:
    """Re-execute one @preview_source builder from its current source file.

    The source is compiled from disk directly, so an explicit reload always
    observes the just-saved text rather than Python bytecode cache timestamps.
    Reload executes in an isolated module namespace so the application's
    imported module is never replaced as a side effect of Preview.
    """
    info = get_preview_source(scene)
    if info is None:
        raise RuntimeError("manual reload requires a Scene built with @preview_source")
    path = Path(info.path).resolve()
    text = path.read_text(encoding="utf-8")
    code = compile(text, str(path), "exec")
    private_name = f"_zanim_preview_reload_{abs(hash(str(path))):x}"
    module_name = (
        f"{info.package_name}.{private_name}" if info.package_name else private_name
    )
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot create module spec for {path}")

    previous = sys.modules.get(module_name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        exec(code, module.__dict__)
        builder = getattr(module, info.builder_name)
        new_scene = builder()
        if not isinstance(new_scene, Scene):
            raise TypeError(f"{info.builder_name}() must return Scene")
        if get_preview_source(new_scene) is None:
            new_scene._close_media_sources()
            raise RuntimeError(
                f"{info.builder_name} must remain decorated with @preview_source"
            )
        return new_scene
    except BaseException:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise
