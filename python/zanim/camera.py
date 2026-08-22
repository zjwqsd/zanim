from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from .object import SceneObject2D
from .space import SE2, Point2, Transform2D, affine2d, as_vec2, pose2d
from .timeline import Easing

if TYPE_CHECKING:
    from .scene import Scene

CameraTransformProvider = Callable[[float], Transform2D]


@dataclass(slots=True)
class Camera2D(SceneObject2D):
    """Scene-owned 2D world-to-view camera.

    ``Scene`` binds its camera immediately, so camera animation is authored
    directly on ``scene.camera`` rather than through ``scene.on(...)``. The
    stored transform always means ``world -> view``; it is deliberately not an
    object local/parent transform.

    A camera is either timeline-driven (the default) or driven by a pure
    absolute-time ``transform_provider``. Keeping these modes exclusive makes
    random-access evaluation unambiguous.
    """

    transform: Transform2D | SE2 = Transform2D()
    opacity: float = 1.0
    z_index: int = 0
    transform_provider: CameraTransformProvider | None = field(default=None, repr=False)
    _scene: "Scene | None" = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._validate_scene_state()
        if self.transform_provider is not None and not callable(self.transform_provider):
            raise TypeError("camera transform_provider must be callable")

    def _bind_scene(self, scene: "Scene") -> None:
        if self._scene is not None and self._scene is not scene:
            raise ValueError("Camera2D is already bound to a different Scene")
        object.__setattr__(self, "_scene", scene)

    def _require_scene(self) -> "Scene":
        if self._scene is None:
            raise RuntimeError("Camera2D animation requires a Scene-bound camera")
        return self._scene

    @property
    def is_dynamic(self) -> bool:
        return self.transform_provider is not None

    def transform_at(self, time: float, initial: Transform2D | None = None) -> Transform2D:
        if self.transform_provider is None:
            return self.transform if initial is None else initial
        value = self.transform_provider(float(time))
        if not isinstance(value, Transform2D):
            raise TypeError("camera transform_provider must return Transform2D")
        return value

    def bounds(self):
        raise TypeError("Camera2D has no object bounds")

    def transform_to(
        self,
        to: Transform2D | SE2,
        *,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Animate to one complete ``world -> view`` transform."""
        return self._require_scene().transform(self, to=to, duration=duration, easing=easing, at=at)

    def pose(
        self,
        *,
        position: Point2,
        rotation: float = 0.0,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Animate to a complete rigid ``world -> view`` pose."""
        return self.transform_to(
            pose2d(position=position, rotation=rotation),
            duration=duration,
            easing=easing,
            at=at,
        )

    def affine(
        self,
        *,
        position: Point2,
        rotation: float = 0.0,
        scale: float | tuple[float, float] = 1.0,
        shear: Point2 = (0.0, 0.0),
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Animate to ``Translation @ Rotation @ Shear @ Scale`` in view space."""
        return self.transform_to(
            affine2d(position=position, rotation=rotation, scale=scale, shear=shear),
            duration=duration,
            easing=easing,
            at=at,
        )

    def transform_function(
        self,
        provider,
        *,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Animate with ``alpha -> complete world-to-view transform``."""
        return self._require_scene().transform_function(
            self, provider, duration=duration, easing=easing, at=at
        )

    def pan(
        self,
        *,
        by: Point2,
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Move the camera by one explicit delta in Scene-world coordinates.

        With ``V`` the current world-to-view transform, camera motion ``d``
        produces ``V' = V @ Translation(-d)``.
        """
        d = as_vec2(by, name="by")
        current = self.transform
        return self.transform_function(
            lambda a: current @ Transform2D.translation(-d.x * a, -d.y * a),
            duration=duration,
            easing=easing,
            at=at,
        )

    def zoom(
        self,
        *,
        by: float,
        about: Point2 = (0.0, 0.0),
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Zoom by a positive factor about one explicit view-space point."""
        factor = float(by)
        if factor <= 0.0:
            raise ValueError("camera zoom factor must be > 0")
        center = as_vec2(about, name="about")
        current = self.transform

        def provider(a: float) -> Transform2D:
            s = 1.0 + (factor - 1.0) * a
            return (
                Transform2D.translation(center.x, center.y)
                @ Transform2D.scaling(s)
                @ Transform2D.translation(-center.x, -center.y)
                @ current
            )

        return self.transform_function(provider, duration=duration, easing=easing, at=at)

    def rotate_view(
        self,
        *,
        by: float,
        about: Point2 = (0.0, 0.0),
        duration: float | None = None,
        easing: Easing = Easing.SMOOTHSTEP,
        at: float = 0.0,
    ):
        """Rotate the camera by ``by`` about one explicit view-space point.

        Camera rotation is opposite world image rotation, hence ``-by`` in the
        world-to-view transform. The path uses exact rotations rather than
        affine coefficient interpolation, so it never shrinks midway.
        """
        center = as_vec2(about, name="about")
        angle = float(by)
        current = self.transform

        def provider(a: float) -> Transform2D:
            return (
                Transform2D.translation(center.x, center.y)
                @ Transform2D.rotation(-angle * a)
                @ Transform2D.translation(-center.x, -center.y)
                @ current
            )

        return self.transform_function(provider, duration=duration, easing=easing, at=at)
