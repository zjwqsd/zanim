import unittest

from zanim import Color
from zanim.mapping import activation_radii, grayscale, signed_weight_colors, weight_widths


class MappingTests(unittest.TestCase):
    def test_grayscale_tracks_value(self):
        self.assertEqual(
            grayscale((0.0, 0.5, 1.0)), (Color(0, 0, 0), Color(128, 128, 128), Color(255, 255, 255))
        )

    def test_signed_weight_mapping_tracks_sign_and_magnitude(self):
        colors = signed_weight_colors((-2.0, 0.0, 1.0), scale=2.0)
        self.assertGreater(colors[0].r, colors[0].b)
        self.assertGreater(colors[2].b, colors[2].r)
        self.assertGreater(colors[0].a, colors[1].a)
        widths = weight_widths((-2.0, 0.0, 1.0), scale=2.0)
        self.assertGreater(widths[0], widths[2])
        self.assertGreater(widths[2], widths[1])

    def test_activation_radius_is_monotonic(self):
        r = activation_radii((0, 0.5, 1))
        self.assertLess(r[0], r[1])
        self.assertLess(r[1], r[2])


if __name__ == "__main__":
    unittest.main()
