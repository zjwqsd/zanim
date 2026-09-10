from __future__ import annotations

import importlib.util
import inspect
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path

from .bound import BoundItem
from .scene import Scene


@dataclass(frozen=True, slots=True)
class PreviewAuthoringInfo:
    """Minimal Preview metadata for object naming and reload context.

    Preview no longer keeps source text, line spans, or clip-to-source mappings.
    Timeline actions are recorded directly by the scheduler.
    """

    path: str
    module_name: str
    package_name: str
    scene_class_name: str | None
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
    scene_class_name: str | None = None


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
    scene_class_name: str | None = None,
) -> Scene:
    if (scene_name is None) == (scene_class_name is None):
        raise ValueError("preview reload needs exactly one of scene_name or scene_class_name")
    scene._preview_reload_info = PreviewReloadInfo(
        path=str(Path(path).resolve()),
        module_name=str(module_name),
        package_name=str(package_name or ""),
        scene_name=scene_name,
        scene_class_name=scene_class_name,
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
    scene_class_name: str | None = None,
) -> Scene:
    scene._preview_authoring_info = PreviewAuthoringInfo(
        path=str(Path(path).resolve()),
        module_name=str(module_name),
        package_name=str(package_name or ""),
        scene_class_name=scene_class_name,
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
    """Capture only Scene hook locals for Preview object naming.

    No source AST, source text, line span, or clip call-site data is retained.
    """
    resolved = Path(path).resolve()
    capture = _RuntimeSourceCapture(resolved, {})
    previous = sys.getprofile()

    def profiler(frame, event, arg):
        if previous is not None:
            previous(frame, event, arg)
        if event != "return":
            return
        try:
            current = Path(frame.f_code.co_filename).resolve()
        except OSError:
            return
        if current != resolved:
            return
        if frame.f_code.co_name in {"setup", "construct"} and isinstance(
            frame.f_locals.get("self"), Scene
        ):
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
    scene_class_name: str | None = None,
) -> Scene:
    """Attach runtime object names captured while executing one scene module."""
    merged = dict(namespace)
    merged.update(capture.return_locals)
    instance_namespace = getattr(scene, "__dict__", None)
    if isinstance(instance_namespace, dict):
        for name, value in instance_namespace.items():
            if not name.startswith("_"):
                merged.setdefault(name, value)
    return _attach_authoring_info(
        scene,
        path=capture.path,
        namespace=merged,
        module_name=module_name,
        package_name=package_name,
        scene_class_name=scene_class_name,
    )


def _resolve_reloaded_scene(module, info: PreviewReloadInfo) -> Scene:
    if info.scene_class_name is not None:
        scene_class = getattr(module, info.scene_class_name, None)
        if (
            not inspect.isclass(scene_class)
            or scene_class is Scene
            or not issubclass(scene_class, Scene)
        ):
            raise RuntimeError(
                f"reload source no longer defines Scene subclass {info.scene_class_name}"
            )
        scene = scene_class()
        scene._run_authoring_hooks()
    else:
        assert info.scene_name is not None
        scene = getattr(module, info.scene_name, None)
    if not isinstance(scene, Scene):
        target = info.scene_class_name or info.scene_name
        raise TypeError(f"reload target {target} must produce Scene")
    return scene


def reload_preview_scene(scene: Scene) -> Scene:
    """Re-execute the file backing a Preview scene in an isolated module."""
    info = get_preview_reload(scene)
    if info is None:
        raise RuntimeError(
            "manual reload requires a Scene subclass or a directly loaded scene script"
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
                scene_class_name=info.scene_class_name,
            )
        attach_preview_reload(
            new_scene,
            path=path,
            module_name=info.module_name,
            package_name=info.package_name,
            scene_name=info.scene_name,
            scene_class_name=info.scene_class_name,
        )
        return new_scene
    except BaseException:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
        raise
