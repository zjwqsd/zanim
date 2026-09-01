import unittest
from dataclasses import dataclass

from zanim import Circle, Scene, Simulation, Transform2D, Vec2
from zanim.ir import SceneIRUnsupported, scene_to_ir


@dataclass
class CounterState:
    x: float = 0.0


def advance_counter(state: CounterState, dt: float):
    state.x += dt


class SimulationTests(unittest.TestCase):
    def test_fixed_step_simulation_is_random_access(self):
        simulation = Simulation(CounterState(), advance_counter, hz=10, checkpoint_interval=0.2)

        a = simulation.state_at(0.75)
        simulation.state_at(0.1)
        b = simulation.state_at(0.75)

        self.assertAlmostEqual(a.x, 0.75)
        self.assertAlmostEqual(b.x, 0.75)
        self.assertGreaterEqual(simulation.checkpoint_count, 4)

    def test_public_state_snapshot_cannot_corrupt_cached_state(self):
        simulation = Simulation(CounterState(), advance_counter, hz=10)
        state = simulation.state_at(0.5)
        state.x = 99.0
        self.assertAlmostEqual(simulation.state_at(0.5).x, 0.5)

    def test_forward_sampling_reuses_latest_fixed_step_state(self):
        calls = 0

        def counted_step(state: CounterState, dt: float):
            nonlocal calls
            calls += 1
            state.x += dt

        simulation = Simulation(CounterState(), counted_step, hz=100, checkpoint_interval=1.0)
        simulation.state_at(0.10)
        simulation.state_at(0.11)
        simulation.state_at(0.12)
        self.assertEqual(calls, 12)

    def test_multiple_objects_bind_to_one_global_state(self):
        simulation = Simulation(CounterState(), advance_counter, hz=20)
        left = Circle(0.2)
        right = Circle(0.2)
        scene = Scene()
        scene.add(left, right)
        scene.bind(left, simulation, position=lambda state: (state.x, 1.0))
        scene.bind(right, simulation, position=lambda state: (-state.x, -1.0))
        scene.wait(1.0)

        snapshot = scene.evaluate(0.4)
        self.assertEqual(len(scene.simulations), 1)
        self.assertAlmostEqual(snapshot.objects[0].snapshot.transform.tx, 0.4)
        self.assertAlmostEqual(snapshot.objects[0].snapshot.transform.ty, 1.0)
        self.assertAlmostEqual(snapshot.objects[1].snapshot.transform.tx, -0.4)
        self.assertAlmostEqual(snapshot.objects[1].snapshot.transform.ty, -1.0)

    def test_position_binding_preserves_linear_transform(self):
        obj = Circle(0.2, transform=Transform2D.scaling(2.0))
        simulation = Simulation(CounterState(), advance_counter)
        scene = Scene()
        scene.add(obj)
        scene.bind(obj, simulation, position=lambda state: Vec2(state.x, 2.0))

        transform = scene.evaluate(0.5).objects[0].snapshot.transform
        self.assertEqual((transform.xx, transform.yy), (2.0, 2.0))
        self.assertAlmostEqual(transform.tx, 0.5)
        self.assertAlmostEqual(transform.ty, 2.0)

    def test_simulation_binding_owns_transform_channel(self):
        obj = Circle(0.2)
        simulation = Simulation(CounterState(), advance_counter)
        scene = Scene()
        scene.add(obj)
        scene.bind(obj, simulation, position=lambda state: (state.x, 0.0))
        with self.assertRaises(TypeError):
            scene.move(obj, to=(1.0, 0.0))

    def test_binding_rejects_existing_transform_clip(self):
        obj = Circle(0.2)
        simulation = Simulation(CounterState(), advance_counter)
        scene = Scene()
        scene.add(obj)
        scene.move(obj, to=(1.0, 0.0), duration=1.0)
        with self.assertRaises(ValueError):
            scene.bind(obj, simulation, position=lambda state: (state.x, 0.0))

    def test_ir_bakes_simulation_binding_when_requested(self):
        obj = Circle(0.2)
        simulation = Simulation(CounterState(), advance_counter, hz=20)
        scene = Scene(fps=10)
        scene.add(obj)
        scene.bind(obj, simulation, position=lambda state: (state.x, 0.0))
        scene.wait(1.0)

        with self.assertRaises(SceneIRUnsupported):
            scene_to_ir(scene)

        ir = scene_to_ir(scene, sample_dynamic_providers=True)
        sampled = [clip for clip in ir["clips"] if clip["kind"] == "sampled_transform"]
        self.assertEqual(len(sampled), 1)
        self.assertEqual(ir["meta"]["sampled_simulation_bindings"], 1)
        self.assertAlmostEqual(sampled[0]["samples"][-1][4], 1.0)


if __name__ == "__main__":
    unittest.main()
