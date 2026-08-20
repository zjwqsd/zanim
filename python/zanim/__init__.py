"""Zanim authoring API.

Internal render snapshots, wire formats and parser helpers intentionally live in
submodules instead of becoming root-package compatibility commitments.
"""

from .batch import BatchObject2D, CircleSet, LineSet, RectSet
from .audio import Audio, AudioObject
from .bounds import Bounds2D
from .camera import Camera2D
from .dynamic import DynamicNumber, NumberFormat
from .formula import (
    FormulaInstance,
    FormulaLiteral,
    FormulaTemplate,
    MatrixSlot,
    NumberSlot,
    ObjectSlot,
    ScriptSlots,
)
from .group import Group2D
from .geometry import (
    Arc,
    Circle,
    Color,
    CubicBezier,
    Ellipse,
    Line,
    Object2D,
    Polygon,
    Polyline,
    Rectangle,
    RegularPolygon,
    Square,
    StrokeStyle,
    Style,
)
from .interpolation import ObjectInterpolation
from .object import DOWN, LEFT, ORIGIN, RIGHT, UP
from .plot import Axes2D, DynamicGeometryObject2D
from .raster import GIF, Image, RasterObject2D, Video
from .shapes import Arrow, Dot, NumberLine
from .scene import Scene
from .space import Canvas, Linear2D, SE2, Transform2D, Vec2
from .svg import load_svg
from .timeline import BatchClip, Easing, InterpolationClip, OpacityClip, PathTrimClip, PlaybackClip, RevealClip, StyleClip, TimeSpan, Timeline, TransformClip, TransformFunctionClip, ValueClip
from .typst import Math, Text
from .value import ScalarValue
from .vector import DynamicVectorObject2D, VectorContour, VectorDocument, VectorObject2D, VectorPath

__all__ = [
    "Arc",
    "Arrow",
    "Axes2D",
    "Bounds2D",
    "Camera2D",
    "BatchClip",
    "BatchObject2D",
    "Canvas",
    "Circle",
    "CircleSet",
    "Color",
    "CubicBezier",
    "DynamicGeometryObject2D",
    "DynamicNumber",
    "DynamicVectorObject2D",
    "Dot",
    "Easing",
    "Ellipse",
    "FormulaInstance",
    "FormulaLiteral",
    "FormulaTemplate",
    "Group2D",
    "InterpolationClip",
    "OpacityClip",
    "PathTrimClip",
    "Line",
    "LineSet",
    "Linear2D",
    "LEFT",
    "Math",
    "MatrixSlot",
    "NumberFormat",
    "NumberSlot",
    "NumberLine",
    "Object2D",
    "ORIGIN",
    "ObjectInterpolation",
    "ObjectSlot",
    "Polygon",
    "Polyline",
    "RectSet",
    "Rectangle",
    "RegularPolygon",
    "RevealClip",
    "RIGHT",
    "SE2",
    "Scene",
    "ScalarValue",
    "ScriptSlots",
    "Square",
    "StrokeStyle",
    "Style",
    "StyleClip",
    "Text",
    "TimeSpan",
    "UP",
    "DOWN",
    "Timeline",
    "Transform2D",
    "TransformClip",
    "TransformFunctionClip",
    "ValueClip",
    "Vec2",
    "VectorContour",
    "VectorDocument",
    "VectorObject2D",
    "VectorPath",
    "load_svg",

    "AlphaMaskSource",
    "Audio",
    "AudioObject",
    "GIF",
    "Image",
    "PlaybackClip",
    "RasterObject2D",
    "SceneRasterSource",
    "Video",
]
