"""Common authoring constants.

These are convenience values only. ``Color(...)``, ``Vec2(...)`` and ordinary
numeric radians remain the complete custom forms.
"""

from math import pi, tau

from .geometry import Color
from .space import Vec2

# Mathematical angles.
PI = pi
TAU = tau
DEGREES = pi / 180.0

# Canonical 2D directions.
ORIGIN = Vec2(0, 0)
RIGHT = Vec2(1, 0)
LEFT = Vec2(-1, 0)
UP = Vec2(0, 1)
DOWN = Vec2(0, -1)

# Default Zanim palette. Colors are immutable, so these are safe to share.
BLUE = Color(96, 166, 255)
GREEN = Color(82, 205, 150)
RED = Color(245, 92, 105)
YELLOW = Color(255, 214, 105)
ORANGE = Color(255, 151, 92)
PURPLE = Color(184, 124, 255)
PINK = Color(245, 92, 145)
CYAN = Color(95, 218, 255)
WHITE = Color(238, 242, 250)
GRAY = Color(145, 158, 184)
MUTED = GRAY
BLACK = Color(0, 0, 0)
TRANSPARENT = Color(0, 0, 0, 0)

__all__ = [
    "BLACK",
    "BLUE",
    "CYAN",
    "DEGREES",
    "DOWN",
    "GRAY",
    "GREEN",
    "LEFT",
    "MUTED",
    "ORANGE",
    "ORIGIN",
    "PI",
    "PINK",
    "PURPLE",
    "RED",
    "RIGHT",
    "TAU",
    "TRANSPARENT",
    "UP",
    "WHITE",
    "YELLOW",
]
