import unittest
from zanim.svg import load_svg, parse_path_data


class SvgTests(unittest.TestCase):
    def test_path_normalizes_line_quadratic_cubic_and_arc(self):
        c = parse_path_data('M 0 0 L 10 0 Q 15 5 10 10 C 8 12 2 12 0 10 A 5 5 0 0 1 0 0 Z')
        self.assertEqual(len(c), 1)
        self.assertTrue(c[0].closed)
        self.assertGreaterEqual(len(c[0].segments), 5)

    def test_svg_use_instances_become_groups(self):
        svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 30 10">
        <defs><path id="g" d="M0 0 L5 0 L5 5 L0 5 Z"/></defs>
        <g fill="#ffffff"><use href="#g" x="0"/><use href="#g" x="10"/></g>
        </svg>'''
        doc = load_svg(svg, unit_scale=1)
        self.assertEqual(len(doc.paths), 2)
        self.assertEqual(doc.group_count, 2)
        self.assertEqual([p.group for p in doc.paths], [0, 1])


if __name__ == '__main__':
    unittest.main()
