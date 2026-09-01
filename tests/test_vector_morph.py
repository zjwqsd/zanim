import unittest

from zanim import BLUE, GREEN, Math, Scene, Text
from zanim.ir import SceneIRUnsupported
from zanim.timeline import VectorMorphClip


class VectorMorphTests(unittest.TestCase):
    def test_text_morph_is_random_access_and_exact_at_endpoints(self):
        source = Text("hello world", font_size=36, color=BLUE)
        target = Text("hello brave world", font_size=42, color=GREEN)
        source_document = source.document
        target_document = target.document
        scene = Scene(fps=30)
        scene.add(source)
        scene.morph(source, to=target, duration=1.0)

        start = scene.evaluate(0.0).vectors[0].snapshot.document
        middle = scene.evaluate(0.5).vectors[0].snapshot.document
        scene.evaluate(0.1)
        middle_again = scene.evaluate(0.5).vectors[0].snapshot.document
        end = scene.evaluate(1.0).vectors[0].snapshot.document

        self.assertEqual(start, source_document)
        self.assertEqual(end, target_document)
        self.assertEqual(middle, middle_again)
        self.assertGreater(middle.group_count, source_document.group_count)
        self.assertEqual(source.content, target.content)

    def test_unchanged_text_glyphs_move_and_restyle_instead_of_whole_object_crossfade(self):
        source = Text("styles", font_size=28, color=BLUE)
        target = Text("styles", font_size=42, color=GREEN)
        scene = Scene()
        scene.add(source)
        clip = scene.morph(source, to=target, duration=1.0)
        self.assertIsInstance(clip, VectorMorphClip)
        self.assertEqual(len(clip.plan.matched), source.document.group_count)
        self.assertFalse(clip.plan.source_only)
        self.assertFalse(clip.plan.target_only)

        middle = scene.evaluate(0.5).vectors[0].snapshot.document
        self.assertEqual(middle.group_count, target.document.group_count)
        self.assertNotEqual(middle.paths[0].fill, clip.before.paths[0].fill)
        self.assertNotEqual(middle.paths[0].fill, clip.after.paths[0].fill)

    def test_math_morph_matches_reused_visual_glyphs(self):
        source = Math("x^2 + y^2 = 1", font_size=42)
        target = Math("x^2 + y^2 = r^2", font_size=42)
        scene = Scene()
        scene.add(source)
        clip = scene.morph(source, to=target, duration=1.0)
        self.assertGreaterEqual(len(clip.plan.matched), 5)
        self.assertGreater(len(clip.plan.target_only), 0)
        self.assertEqual(scene.evaluate(1.0).vectors[0].snapshot.document, target.document)

    def test_chained_text_morph_uses_latest_semantic_content(self):
        source = Text("abc", font_size=32)
        middle = Text("axc", font_size=32)
        target = Text("axyc", font_size=32)
        scene = Scene()
        scene.add(source)
        scene.morph(source, to=middle, duration=1.0)
        second = scene.morph(source, to=target, duration=1.0)
        self.assertEqual(source.content, target.content)
        self.assertGreaterEqual(len(second.plan.matched), 3)
        self.assertEqual(scene.evaluate(2.0).vectors[0].snapshot.document, target.document)

    def test_ir_requires_explicit_bake_and_preview_form_is_sampled_vector(self):
        source = Text("a+b", font_size=32)
        target = Text("a+b+c", font_size=32)
        scene = Scene(fps=24)
        scene.add(source)
        scene.morph(source, to=target, duration=1.0)
        with self.assertRaises(SceneIRUnsupported):
            scene.to_ir()

        ir = scene.to_ir(sample_dynamic_providers=True)
        record = next(obj for obj in ir["objects"] if obj["id"] == 1)
        self.assertEqual(record["kind"], "sampled_vector2d")
        self.assertEqual(record["state"]["sample_rate"], 24)


if __name__ == "__main__":
    unittest.main()
