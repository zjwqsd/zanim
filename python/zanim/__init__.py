"""Zanim authoring API.

Internal render snapshots, wire formats and parser helpers intentionally live in
submodules instead of becoming root-package compatibility commitments.
"""

from .batch import BatchObject2D, CircleSet, LineSet, RectSet
from .audio import Audio, AudioObject
from .bounds import Bounds2D
from .camera import Camera2D
from .camera3d import Camera3D
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
from .raster import AlphaMaskSource, GIF, Image, RasterObject2D, SceneRasterSource, Video
from .shapes import Arrow, Dot, NumberLine
from .scene import Scene
from .mesh3d import Box3D, Cube3D, MeshObject3D, Surface3D, TriangleMesh
from .space import Canvas, Linear2D, SE2, Transform2D, Vec2
from .space3d import SO3, Transform3D, Vec3
from .svg import load_svg
from .timeline import BatchClip, Easing, InterpolationClip, OpacityClip, PathTrimClip, PlaybackClip, RevealClip, StyleClip, TimeSpan, Timeline, TransformClip, TransformFunctionClip, Transform3DClip, Transform3DFunctionClip, ValueClip
from .typst import Math, Text
from .value import ScalarValue
from .vector import DynamicVectorObject2D, VectorContour, VectorDocument, VectorObject2D, VectorPath

__all__ = [
    "Arc",
    "Arrow",
    "Axes2D",
    "Bounds2D",
    "Box3D",
    "Camera2D",
    "Camera3D",
    "BatchClip",
    "BatchObject2D",
    "Canvas",
    "Circle",
    "CircleSet",
    "Color",
    "CubicBezier",
    "Cube3D",
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
    "MeshObject3D",
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
    "SO3",
    "ScalarValue",
    "ScriptSlots",
    "Square",
    "StrokeStyle",
    "Style",
    "StyleClip",
    "Surface3D",
    "Text",
    "TimeSpan",
    "UP",
    "DOWN",
    "Timeline",
    "TriangleMesh",
    "Transform2D",
    "Transform3D",
    "TransformClip",
    "Transform3DClip",
    "TransformFunctionClip",
    "Transform3DFunctionClip",
    "ValueClip",
    "Vec2",
    "Vec3",
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
