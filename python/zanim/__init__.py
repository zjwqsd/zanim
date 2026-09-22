"""Zanim's public authoring API.

Define class-based scenes directly in ``Scene.construct()`` for the common case;
``Scene.setup()`` is an optional organization hook for heavier declaration or resource
preparation. ``Scene.add()`` is the ownership boundary between raw initial authoring
and Scene-owned timeline state. The root package exposes the objects and values used
for authoring; scheduler, bound handle, wire-format, and render implementation types
live in submodules.
"""

from ._version import __version__
from .audio import Audio
from .batch import BatchObject2D, CircleSet, DynamicBatchObject2D, LineSet, RectSet
from .boolean import Difference, Exclusion, Intersection, Union
from .camera import Camera2D
from .camera3d import Camera3D
from .constants import (
    BLACK,
    BLUE,
    CYAN,
    DEFAULT_STROKE_WIDTH,
    DEGREES,
    DOWN,
    GRAY,
    GREEN,
    LEFT,
    MUTED,
    ORANGE,
    ORIGIN,
    PI,
    PINK,
    PURPLE,
    RED,
    RIGHT,
    TAU,
    TRANSPARENT,
    UP,
    WHITE,
    YELLOW,
)
from .dynamic import DynamicNumber, NumberFormat
from .expression import TIME, ScalarExpr, X
from .formula import (
    FormulaLiteral,
    FormulaTemplate,
    MatrixSlot,
    NumberSlot,
    ObjectSlot,
    ScriptSlots,
)
from .fourier import FourierEpicycles, FourierTerm
from .fractal import JuliaSet, MandelbrotSet
from .geometry import Color
from .group import Group
from .group3d import Group3D
from .infinite import ComplexMappedGrid, InfiniteGrid, InfiniteLine, NumberPlane
from .layout import (
    BOTTOM,
    BOTTOM_LEFT,
    BOTTOM_RIGHT,
    CENTER,
    LEFT_CENTER,
    RIGHT_CENTER,
    TOP,
    TOP_LEFT,
    TOP_RIGHT,
    Column,
    Frame,
    Grid,
    Row,
)
from .mesh3d import Box3D, Cube3D, Surface3D
from .plot import Axes, DynamicGeometryObject2D, FunctionPlot
from .raster import GIF, ArrayImage, Image, SceneViewport, Video
from .scene import Scene
from .shapes import (
    Arc,
    Arrow,
    Brace,
    Circle,
    CubicBezier,
    Dot,
    Ellipse,
    Line,
    NumberLine,
    Polygon,
    Polyline,
    Rectangle,
    RegularPolygon,
    Square,
    SurroundingRectangle,
)
from .simulation import Simulation
from .space import (
    LOCAL,
    PARENT,
    SE2,
    WORLD,
    Canvas,
    Transform2D,
    Vec2,
    affine2d,
)
from .space3d import SE3, SO3, Transform3D, Vec3
from .svg import load_svg
from .timeline import Easing
from .typst import Math, Text
from .value import ScalarValue
from .vector import DynamicVectorObject2D, VectorObject2D
from .vector_field import DynamicVectorField, VectorField

__all__ = [
    "__version__",
    "Scene",
    "SceneViewport",
    "Exclusion",
    "Difference",
    "Union",
    "Intersection",
    "Simulation",
    "BatchObject2D",
    "DynamicBatchObject2D",
    "LineSet",
    "CircleSet",
    "RectSet",
    "VectorField",
    "DynamicVectorField",
    "Canvas",
    "Circle",
    "Square",
    "SurroundingRectangle",
    "Rectangle",
    "Ellipse",
    "Arc",
    "Brace",
    "RegularPolygon",
    "Line",
    "InfiniteLine",
    "InfiniteGrid",
    "NumberPlane",
    "ComplexMappedGrid",
    "MandelbrotSet",
    "JuliaSet",
    "FourierTerm",
    "FourierEpicycles",
    "Polyline",
    "Polygon",
    "CubicBezier",
    "Dot",
    "Arrow",
    "NumberLine",
    "Group",
    "Group3D",
    "Text",
    "Math",
    "VectorObject2D",
    "DynamicVectorObject2D",
    "Color",
    "BLUE",
    "GREEN",
    "RED",
    "YELLOW",
    "ORANGE",
    "PURPLE",
    "PINK",
    "CYAN",
    "WHITE",
    "GRAY",
    "MUTED",
    "BLACK",
    "TRANSPARENT",
    "PI",
    "TAU",
    "DEGREES",
    "DEFAULT_STROKE_WIDTH",
    "Vec2",
    "Transform2D",
    "SE2",
    "SE3",
    "affine2d",
    "LOCAL",
    "PARENT",
    "WORLD",
    "ORIGIN",
    "RIGHT",
    "LEFT",
    "UP",
    "DOWN",
    "Frame",
    "Row",
    "Column",
    "Grid",
    "CENTER",
    "TOP",
    "BOTTOM",
    "LEFT_CENTER",
    "RIGHT_CENTER",
    "TOP_LEFT",
    "TOP_RIGHT",
    "BOTTOM_LEFT",
    "BOTTOM_RIGHT",
    "Easing",
    "Camera2D",
    "Axes",
    "ScalarExpr",
    "X",
    "TIME",
    "FunctionPlot",
    "ScalarValue",
    "DynamicGeometryObject2D",
    "load_svg",
    "DynamicNumber",
    "NumberFormat",
    "FormulaLiteral",
    "FormulaTemplate",
    "MatrixSlot",
    "NumberSlot",
    "ObjectSlot",
    "ScriptSlots",
    "Image",
    "GIF",
    "Video",
    "ArrayImage",
    "Audio",
    "Camera3D",
    "Vec3",
    "Transform3D",
    "SO3",
    "Box3D",
    "Cube3D",
    "Surface3D",
]
