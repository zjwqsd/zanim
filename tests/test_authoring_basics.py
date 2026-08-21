import unittest

from zanim import (
    Arrow, Canvas, Color, Dot, DOWN, DynamicNumber, LEFT, NumberFormat, PARENT,
    NumberLine, Object2D, RIGHT, Scene, ScalarValue, Square, Style,
    Transform2D, UP, Vec2,
)
from zanim.render.wire import encode_snapshot


class AuthoringBasicsTests(unittest.TestCase):
    def test_to_edge(self):
        obj = Object2D(Square(1))
        canvas = Canvas(width=800, height=600, unit_size=100)
        obj.to_edge(canvas, RIGHT, buff=.25)
        self.assertAlmostEqual(obj.bounds().right, 3.75)
        obj.to_edge(canvas, UP, buff=.5)
        self.assertAlmostEqual(obj.bounds().top, 2.5)

    def test_common_shapes(self):
        dot = Dot(Vec2(1, 2))
        self.assertAlmostEqual(dot.bounds().center.x, 1)
        arrow = Arrow(Vec2(0,0), Vec2(2,1))
        self.assertEqual(len(arrow.children), 2)
        line = NumberLine((-2, 2), length=8)
        self.assertAlmostEqual(line.n2p(1).x, 2)
        labeled = NumberLine((-1, 1), length=4, include_numbers=True, label_font_size=12)
        self.assertGreater(len(labeled.children), 2)

    def test_scalar_value_binds_directly_to_dynamic_number(self):
        value = ScalarValue(1)
        scene = Scene()
        scene.add(value)
        number = DynamicNumber(value, number_format=NumberFormat(width=3), font_size=20)
        scene.add(number)
        scene.value(value, to=5, duration=1)
        self.assertAlmostEqual(value.value_at(.5), 3)
        self.assertIsNot(number._document_at(.5, number.document), number._document_at(0, number.document))

    def test_vec2_arithmetic_is_authoring_friendly(self):
        point = 3 * RIGHT + 2 * UP - LEFT
        self.assertEqual(point, Vec2(4, 2))
        self.assertAlmostEqual(Vec2(3, 4).length, 5)
        self.assertEqual(Vec2(3, 4).normalized(), Vec2(0.6, 0.8))

    def test_layout_mutators_are_initial_state_only_after_scene_registration(self):
        obj = Object2D(Square(1))
        obj.shift(RIGHT)
        scene = Scene()
        scene.add(obj)
        with self.assertRaisesRegex(RuntimeError, "Scene timeline operations"):
            obj.shift(UP)
        scene.move(obj, by=UP, frame=PARENT, duration=1)
        self.assertEqual(obj.center, Vec2(1, 1))

    def test_explicit_move_changes_the_same_object(self):
        obj = Object2D(Square(1))
        scene = Scene()
        scene.add(obj)
        scene.move(obj, by=2 * RIGHT + UP, frame=PARENT, duration=2)

        self.assertIs(scene.objects[0], obj)
        self.assertEqual(len(scene.objects), 1)
        self.assertEqual(scene.evaluate(1).transients, ())
        self.assertAlmostEqual(scene.evaluate(1).objects[0].snapshot.transform.tx, 1.0)
        self.assertAlmostEqual(scene.evaluate(1).objects[0].snapshot.transform.ty, 0.5)
        self.assertEqual(obj.center, Vec2(2, 1))

    def test_move_to_uses_explicit_center_target(self):
        obj = Object2D(Square(2), transform=Transform2D.translation(-3, 1))
        scene = Scene()
        scene.add(obj)
        scene.move(obj, to=Vec2(4, -2), duration=1)
        self.assertEqual(obj.center, Vec2(4, -2))
        end = scene.evaluate(1).objects[0].snapshot.transform
        self.assertAlmostEqual(end.tx, 4)
        self.assertAlmostEqual(end.ty, -2)

    def test_rotate_and_scale_require_explicit_pivot(self):
        obj = Object2D(Square(2), transform=Transform2D.translation(2, 0))
        scene = Scene()
        scene.add(obj)
        pivot = obj.center
        scene.rotate(obj, by=3.141592653589793 / 2, about=pivot, duration=1)
        self.assertAlmostEqual(obj.center.x, 2)
        self.assertAlmostEqual(obj.center.y, 0)
        scene.scale(obj, by=2, about=obj.center, duration=1)
        self.assertAlmostEqual(obj.center.x, 2)
        self.assertAlmostEqual(obj.bounds().width, 4)

    def test_transform_by_and_to_are_explicit_and_seekable(self):
        obj = Object2D(Square(1), transform=Transform2D.translation(1, 0))
        scene = Scene()
        scene.add(obj)
        scene.transform(obj, by=Transform2D.translation(2, 0), frame=PARENT, duration=1)
        self.assertAlmostEqual(scene.evaluate(.5).objects[0].snapshot.transform.tx, 2)
        self.assertAlmostEqual(obj.transform.tx, 3)
        scene.transform(obj, to=Transform2D.translation(-1, 0), duration=1)
        self.assertAlmostEqual(obj.transform.tx, -1)
        with self.assertRaises(ValueError):
            scene.transform(obj)
        with self.assertRaises(ValueError):
            scene.transform(obj, by=Transform2D(), to=Transform2D())

    def test_target_state_aliases_keep_explicit_to_keyword(self):
        obj = Object2D(Square(1), style=Style.solid(Color(10, 20, 30)))
        scene = Scene()
        scene.add(obj)
        scene.style(obj, to=Style.solid(Color(30, 20, 10)), duration=.5)
        scene.opacity(obj, to=.25, duration=.5)
        self.assertEqual(obj.style.fill, Color(30, 20, 10))
        self.assertAlmostEqual(obj.opacity, .25)

    def test_set_transform_is_an_explicit_instantaneous_timeline_event(self):
        obj = Object2D(Square(1))
        scene = Scene()
        scene.add(obj)
        scene.wait(1)
        scene.set_transform(obj, to=Transform2D.translation(5, 0))
        self.assertAlmostEqual(scene.evaluate(.9).objects[0].snapshot.transform.tx, 0)
        self.assertAlmostEqual(scene.evaluate(1.0).objects[0].snapshot.transform.tx, 5)

    def test_style_factories_do_not_add_hidden_components(self):
        color = Color(10, 20, 30)
        solid = Style.solid(color)
        self.assertEqual(solid.fill, color)
        self.assertIsNone(solid.stroke)
        outline = Style.outline(color, .07)
        self.assertIsNone(outline.fill)
        self.assertEqual(outline.stroke.color, color)
        painted = Style.paint(Color(1, 2, 3), color, .05)
        self.assertEqual(painted.fill, Color(1, 2, 3))
        self.assertEqual(painted.stroke.width, .05)

    def test_add_and_remove_define_half_open_lifetime(self):
        scene = Scene()
        scene.wait(2)
        obj = Object2D(Square(1))
        scene.add(obj)
        self.assertEqual(scene.evaluate(1.99).objects, ())
        self.assertEqual(len(scene.evaluate(2.0).objects), 1)
        scene.wait(1)
        scene.remove(obj)
        self.assertEqual(len(scene.evaluate(2.99).objects), 1)
        self.assertEqual(scene.evaluate(3.0).objects, ())
        self.assertEqual(obj.opacity, 1.0)

    def test_group_lifetime_controls_children(self):
        a = Object2D(Square(1))
        b = Object2D(Square(1)).shift(2 * RIGHT)
        group = __import__('zanim').Group2D([a, b])
        scene = Scene()
        scene.add(group)
        self.assertEqual(len(scene.evaluate(0).objects), 2)
        scene.wait(1)
        scene.remove(group)
        self.assertEqual(scene.evaluate(1).objects, ())
        with self.assertRaisesRegex(ValueError, "outside object lifetime"):
            scene.move(a, by=RIGHT, frame=PARENT, duration=.2)

    def test_lifetime_boundaries_are_not_parallel_operations(self):
        scene = Scene()
        obj = Object2D(Square(1))
        with self.assertRaisesRegex(ValueError, "not allowed inside parallel"):
            with scene.parallel():
                scene.add(obj)

    def test_animation_cannot_be_scheduled_before_add(self):
        scene = Scene()
        scene.wait(2)
        obj = Object2D(Square(1))
        scene.add(obj)
        with self.assertRaisesRegex(ValueError, "before object lifetime begins"):
            scene.transform(obj, to=Transform2D.translation(1, 0), duration=.5, at=-1)

    def test_registered_state_cannot_be_assigned_without_time(self):
        obj = Object2D(Square(1))
        scene = Scene()
        scene.add(obj)
        with self.assertRaisesRegex(RuntimeError, "after Scene.add"):
            obj.opacity = 0.0
        with self.assertRaisesRegex(RuntimeError, "after Scene.add"):
            obj.transform = Transform2D.translation(1, 0)
        scene.opacity(obj, to=0.5, duration=.2)
        self.assertAlmostEqual(obj.opacity, .5)

        value = ScalarValue(1)
        value_scene = Scene()
        value_scene.add(value)
        with self.assertRaisesRegex(RuntimeError, "after Scene.add"):
            value.value = 2
        value_scene.value(value, to=2, duration=.2)
        self.assertEqual(value.value, 2)

    def test_create_requires_explicit_trim_zero(self):
        obj = Object2D(Square(1))
        scene = Scene()
        scene.add(obj)
        with self.assertRaisesRegex(ValueError, "current trim to be 0"):
            scene.create(obj)

    def test_z_index_precedes_insertion_order(self):
        back = Object2D(Square(2), z_index=-1)
        front = Object2D(Square(1), z_index=5)
        scene = Scene()
        scene.add(front, back)
        encoded = encode_snapshot(scene.evaluate(0))
        # back was inserted second but must be first in the draw stream.
        self.assertEqual(encoded.draw_items[0].index, 1)
        self.assertEqual(encoded.draw_items[1].index, 0)


if __name__ == '__main__': unittest.main()
