import importlib.util
import sys
import unittest
from pathlib import Path

from zanim import ComplexMappedGrid

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "examples" / "extras" / "complex_mapping.py"
SPEC = importlib.util.spec_from_file_location("zanim_complex_mapping_extra", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ComplexMappingExtraTests(unittest.TestCase):
    def test_scene_uses_only_native_complex_grids_for_mapping_geometry(self):
        scene = MODULE.build_scene()
        grids = [item for item in scene.items if isinstance(item, ComplexMappedGrid)]
        self.assertEqual(len(grids), 4)  # all four mappings animate natively
        for t in (0.0, scene.duration * 0.25, scene.duration * 0.55, scene.duration):
            snapshot = scene.evaluate(t)
            self.assertEqual(len(snapshot.batches), 0)

    def test_scene_builds_random_access(self):
        scene = MODULE.build_scene()
        self.assertGreater(scene.duration, 0.0)
        for t in (0.0, scene.duration * 0.33, scene.duration * 0.78, scene.duration):
            scene.evaluate(t)


if __name__ == "__main__":
    unittest.main()
