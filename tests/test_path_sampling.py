import math
import unittest

from zanim.geometry import CubicBezier
from zanim.path import flatten_cubic, resample_polyline_by_arclength, sample_vector_contour_by_arclength
from zanim.space import Vec2
from zanim.vector import VectorContour


class PathSamplingTests(unittest.TestCase):
    def test_closed_square_is_uniformly_resampled_without_duplicate_endpoint(self):
        contour = VectorContour((
            CubicBezier(Vec2(0,0), Vec2(1/3,0), Vec2(2/3,0), Vec2(1,0)),
            CubicBezier(Vec2(1,0), Vec2(1,1/3), Vec2(1,2/3), Vec2(1,1)),
            CubicBezier(Vec2(1,1), Vec2(2/3,1), Vec2(1/3,1), Vec2(0,1)),
            CubicBezier(Vec2(0,1), Vec2(0,2/3), Vec2(0,1/3), Vec2(0,0)),
        ), True)
        points = sample_vector_contour_by_arclength(contour, 8)
        self.assertEqual(len(points), 8)
        self.assertNotEqual(points[0], points[-1])
        distances = [
            math.hypot(b.x-a.x, b.y-a.y)
            for a,b in zip(points, (*points[1:], points[0]))
        ]
        self.assertLess(max(distances) - min(distances), 1e-8)

    def test_flatten_curved_cubic_refines(self):
        curve = CubicBezier(Vec2(0,0), Vec2(0,1), Vec2(1,1), Vec2(1,0))
        coarse = flatten_cubic(curve, tolerance=0.2)
        fine = flatten_cubic(curve, tolerance=0.01)
        self.assertGreater(len(fine), len(coarse))

    def test_open_resample_keeps_endpoints(self):
        points = resample_polyline_by_arclength((Vec2(0,0), Vec2(3,0)), 4, closed=False)
        self.assertEqual(points[0], Vec2(0,0))
        self.assertEqual(points[-1], Vec2(3,0))
        self.assertAlmostEqual(points[1].x, 1.0)
