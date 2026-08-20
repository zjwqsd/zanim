import math
import unittest

from zanim import Canvas, Linear2D, Transform2D, Vec2


class CoordinateSystemTests(unittest.TestCase):
    def test_center_origin_x_right_y_up(self):
        canvas = Canvas(width=800, height=600, unit_size=100)
        self.assertEqual(canvas.world_to_device(Vec2(0, 0)), Vec2(400, 300))
        self.assertEqual(canvas.world_to_device(Vec2(1, 1)), Vec2(500, 200))

    def test_positive_rotation_goes_visually_counter_clockwise(self):
        canvas = Canvas(width=800, height=600, unit_size=100)
        view = Transform2D.rotation(math.pi / 2)
        point = canvas.world_to_device(Vec2(1, 0), view)
        self.assertAlmostEqual(point.x, 400)
        self.assertAlmostEqual(point.y, 200)

    def test_matrix_composition(self):
        model = Transform2D.translation(2, 3) @ Transform2D.scaling(2)
        self.assertEqual(model.apply(Vec2(1, 1)), Vec2(4, 5))

    def test_general_linear_map(self):
        linear = Linear2D(1.0, 0.5, -0.25, 2.0)
        p = linear.apply(Vec2(2, 4))
        self.assertEqual(p, Vec2(4, 7.5))

    def test_instance_transform_methods_compose_instead_of_replacing(self):
        t = Transform2D.translation(2, 3).rotate(math.pi / 2)
        origin = t.apply(Vec2())
        x_axis = t.apply(Vec2(1, 0))
        self.assertAlmostEqual(origin.x, 2)
        self.assertAlmostEqual(origin.y, 3)
        self.assertAlmostEqual(x_axis.x, 2)
        self.assertAlmostEqual(x_axis.y, 4)




if __name__ == "__main__":
    unittest.main()
