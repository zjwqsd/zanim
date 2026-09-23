from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, replace
from typing import Any, Iterator, Mapping

from .geometry import Color


@dataclass(frozen=True, slots=True)
class CanvasTheme:
    width: int = 1920
    height: int = 1080
    unit_size: float = 135.0
    fps: int = 60
    background: Color = Color(0, 0, 0)

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("theme canvas dimensions must be positive")
        if self.unit_size <= 0:
            raise ValueError("theme canvas unit_size must be positive")
        if self.fps <= 0:
            raise ValueError("theme canvas fps must be positive")


@dataclass(frozen=True, slots=True)
class StyleTheme:
    fill: Color | None = None
    stroke: Color | None = Color(255, 255, 255)
    stroke_width: float = 4.0 / 135.0

    def __post_init__(self) -> None:
        if self.stroke_width < 0:
            raise ValueError("theme stroke_width must be >= 0")


@dataclass(frozen=True, slots=True)
class TextTheme:
    font_size: float = 48.0
    color: Color = Color(255, 255, 255)
    font: str | tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.font_size <= 0:
            raise ValueError("theme font_size must be positive")


@dataclass(frozen=True, slots=True)
class AnimationTheme:
    duration: float = 1.0
    wait_duration: float = 1.0
    easing: str = "smooth"

    def __post_init__(self) -> None:
        if self.duration < 0 or self.wait_duration < 0:
            raise ValueError("theme animation durations must be >= 0")
        if self.easing not in {"linear", "smoothstep", "smooth"}:
            raise ValueError("theme easing must be linear, smoothstep, or smooth")


@dataclass(frozen=True, slots=True)
class ShapeTheme:
    dot_radius: float = 0.08
    arrow_tip_length: float = 0.35
    arrow_tip_width: float = 0.35
    arrow_buff: float = 0.25

    def __post_init__(self) -> None:
        if self.dot_radius <= 0:
            raise ValueError("theme dot_radius must be positive")
        if min(self.arrow_tip_length, self.arrow_tip_width, self.arrow_buff) < 0:
            raise ValueError("theme arrow dimensions must be >= 0")


@dataclass(frozen=True, slots=True)
class Theme:
    name: str
    canvas: CanvasTheme = CanvasTheme()
    style: StyleTheme = StyleTheme()
    text: TextTheme = TextTheme()
    math: TextTheme = TextTheme()
    animation: AnimationTheme = AnimationTheme()
    shape: ShapeTheme = ShapeTheme()
    mesh3d_color: Color = Color(88, 196, 221)

    def with_overrides(self, values: Mapping[str, Any]) -> "Theme":
        theme: Theme = self
        for section in ("canvas", "style", "text", "math", "animation", "shape"):
            raw = values.get(section)
            if raw is None:
                continue
            if not isinstance(raw, Mapping):
                raise TypeError(f"theme.{section} must be a mapping")
            current = getattr(theme, section)
            parsed = _parse_section(section, raw)
            theme = replace(theme, **{section: replace(current, **parsed)})
        if "mesh3d_color" in values:
            color = _color(values["mesh3d_color"])
            if color is None:
                raise ValueError("theme mesh3d_color cannot be null")
            theme = replace(theme, mesh3d_color=color)
        if "name" in values:
            theme = replace(theme, name=str(values["name"]))
        return theme

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for section in ("canvas", "style", "text", "math"):
            for key, value in list(data[section].items()):
                if isinstance(value, dict) and {"r", "g", "b", "a"} <= value.keys():
                    data[section][key] = _color_hex(Color(**value))
        data["mesh3d_color"] = _color_hex(self.mesh3d_color)
        return data


def _color(value: Any) -> Color | None:
    if value is None or isinstance(value, Color):
        return value
    if isinstance(value, str):
        raw = value.strip().lstrip("#")
        if len(raw) not in (6, 8):
            raise ValueError(f"invalid color {value!r}")
        parts = [int(raw[i : i + 2], 16) for i in range(0, len(raw), 2)]
        if len(parts) == 3:
            parts.append(255)
        return Color(*parts)
    if isinstance(value, (tuple, list)) and len(value) in (3, 4):
        parts = [int(v) for v in value]
        if len(parts) == 3:
            parts.append(255)
        return Color(*parts)
    raise TypeError("color must be Color, #RRGGBB[/AA], RGB(A) sequence, or None")


def _color_hex(color: Color | None) -> str | None:
    if color is None:
        return None
    suffix = "" if color.a == 255 else f"{color.a:02x}"
    return f"#{color.r:02x}{color.g:02x}{color.b:02x}{suffix}"


def _parse_section(section: str, raw: Mapping[str, Any]) -> dict[str, Any]:
    values = dict(raw)
    color_keys = {
        "canvas": {"background"},
        "style": {"fill", "stroke"},
        "text": {"color"},
        "math": {"color"},
    }.get(section, set())
    for key in color_keys & values.keys():
        values[key] = _color(values[key])
    if "font" in values and isinstance(values["font"], list):
        values["font"] = tuple(str(v) for v in values["font"])
    return values


# Zanim's first built-in theme intentionally follows Manim's ordinary authoring
# defaults (black stage, white 4px-ish strokes, 48pt text, 60fps, 1s actions).
MANIM = Theme(name="manim")

_THEMES: dict[str, Theme] = {MANIM.name: MANIM}
_CURRENT_THEME: ContextVar[Theme] = ContextVar("zanim_theme", default=MANIM)


def register_theme(theme: Theme, *, replace_existing: bool = False) -> Theme:
    if not isinstance(theme, Theme):
        raise TypeError("theme must be Theme")
    if theme.name in _THEMES and not replace_existing:
        raise ValueError(f"theme {theme.name!r} is already registered")
    _THEMES[theme.name] = theme
    return theme


def theme_named(name: str) -> Theme:
    try:
        return _THEMES[str(name)]
    except KeyError as exc:
        raise KeyError(
            f"unknown Zanim theme {name!r}; available: {', '.join(sorted(_THEMES))}"
        ) from exc


def get_theme() -> Theme:
    return _CURRENT_THEME.get()


def set_theme(theme: str | Theme) -> Theme:
    resolved = theme_named(theme) if isinstance(theme, str) else theme
    if not isinstance(resolved, Theme):
        raise TypeError("theme must be a registered name or Theme")
    _CURRENT_THEME.set(resolved)
    return resolved


@contextmanager
def use_theme(theme: str | Theme) -> Iterator[Theme]:
    resolved = theme_named(theme) if isinstance(theme, str) else theme
    if not isinstance(resolved, Theme):
        raise TypeError("theme must be a registered name or Theme")
    token = _CURRENT_THEME.set(resolved)
    try:
        yield resolved
    finally:
        _CURRENT_THEME.reset(token)


__all__ = [
    "AnimationTheme",
    "CanvasTheme",
    "MANIM",
    "ShapeTheme",
    "StyleTheme",
    "TextTheme",
    "Theme",
    "get_theme",
    "register_theme",
    "set_theme",
    "theme_named",
    "use_theme",
]
