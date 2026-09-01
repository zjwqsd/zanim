from __future__ import annotations

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

F = TypeVar("F", bound=Callable[..., Scene])


@dataclass(frozen=True, slots=True)
class PreviewAuthoringInfo:
    """Minimal Preview metadata for object naming and reload context.

    Preview no longer keeps source text, line spans, or clip-to-source mappings.
    Timeline actions are recorded directly by the scheduler.
    """

    path: str
    module_name: str
    package_name: str
    builder_name: str | None
    object_names: dict[int, tuple[str, ...]]

    def primary_name(self, object_id: int) -> str | None:
        names = self.object_names.get(int(object_id), ())
        return names[0] if names else None


# Compatibility name for callers that imported the old helper type.
PreviewSourceInfo = PreviewAuthoringInfo


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


def get_preview_authoring(scene: Scene) -> PreviewAuthoringInfo | None:
    value = scene._preview_authoring_info
    return value if isinstance(value, PreviewAuthoringInfo) else None


# Compatibility accessor. It now returns naming/reload metadata only.
def get_preview_source(scene: Scene) -> PreviewAuthoringInfo | None:
    return get_preview_authoring(scene)


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


def _object_names(scene: Scene, namespace: dict[str, object]) -> dict[int, tuple[str, ...]]:
    names: dict[int, list[str]] = {}
    by_identity = {id(item.object_ref): item.object_id for item in scene._registry}
    for name, value in namespace.items():
        raw = value.raw if isinstance(value, BoundItem) else value
        object_id = by_identity.get(id(raw))
        if object_id is None:
            continue
        entries = names.setdefault(object_id, [])
        if name not in entries:
            entries.append(name)
    return {object_id: tuple(entries) for object_id, entries in names.items()}


def _attach_authoring_info(
    scene: Scene,
    *,
    path: str | Path,
    namespace: dict[str, object],
    module_name: str,
    package_name: str = "",
    builder_name: str | None = None,
) -> Scene:
    scene._preview_authoring_info = PreviewAuthoringInfo(
        path=str(Path(path).resolve()),
        module_name=str(module_name),
        package_name=str(package_name or ""),
        builder_name=builder_name,
        object_names=_object_names(scene, namespace),
    )
    return scene


def infer_script_reload(scene: Scene, frame) -> None:
    """Attach naming and reload metadata for a top-level ``scene.preview()`` script."""
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
    if get_preview_authoring(scene) is None:
        _attach_authoring_info(
            scene,
            path=path,
            namespace=frame.f_globals,
            module_name=module_name,
            package_name=package_name,
        )
    attach_preview_reload(
        scene,
        path=path,
        module_name=module_name,
        package_name=package_name,
        scene_name=scene_name,
    )


@dataclass(slots=True)
class _RuntimeSourceCapture:
    path: Path
    return_locals: dict[str, object]


@contextmanager
def capture_runtime_source(path: str | Path):
    """Capture only Scene-builder return locals for Preview object naming.

    No source AST, source text, line span, or clip call-site data is retained.
    """
    resolved = Path(path).resolve()
    capture = _RuntimeSourceCapture(resolved, {})
    previous = sys.getprofile()

    def profiler(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event != "return" or not isinstance(arg, Scene):
            return
        try:
            current = Path(frame.f_code.co_filename).resolve()
        except OSError:
            return
        if current == resolved:
            capture.return_locals.update(frame.f_locals)

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
    """Attach runtime object names captured while executing one scene module."""
    merged = dict(namespace)
    merged.update(capture.return_locals)
    return _attach_authoring_info(
        scene,
        path=capture.path,
        namespace=merged,
        module_name=module_name,
        package_name=package_name,
        builder_name=builder_name,
    )


def preview_source(func: F) -> F:
    """Compatibility decorator that captures local object names for Preview.

    Source-location tracking has been removed. The decorator is retained so
    existing scenes keep their object labels and reload behavior unchanged.
    """
    path = Path(inspect.getsourcefile(func) or inspect.getfile(func)).resolve()

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        with capture_runtime_source(path) as capture:
            scene = func(*args, **kwargs)
        if not isinstance(scene, Scene):
            raise TypeError("@preview_source function must return Scene")
        package_name = str(func.__globals__.get("__package__") or "")
        attach_runtime_source(
            scene,
            capture,
            func.__globals__,
            module_name=func.__module__,
            package_name=package_name,
            builder_name=func.__name__,
        )
        attach_preview_reload(
            scene,
            path=path,
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
            "manual reload requires either a Preview builder or a directly loaded scene script"
        )
    path = Path(info.path).resolve()
    code = compile(path.read_text(encoding="utf-8"), str(path), "exec")
    private_name = f"_zanim_preview_reload_{abs(hash(str(path))):x}"
    module_name = f"{info.package_name}.{private_name}" if info.package_name else private_name
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot create module spec for {path}")

    previous = sys.modules.get(module_name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        with capture_runtime_source(path) as capture:
            with suppress_preview_calls():
                exec(code, module.__dict__)
            new_scene = _resolve_reloaded_scene(module, info)
        if get_preview_authoring(new_scene) is None:
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
