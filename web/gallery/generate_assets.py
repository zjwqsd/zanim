from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
from zanim.cli import _load_scene
from zanim.ir import scene_to_ir

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "web/gallery/generated"
(OUT / "ir").mkdir(parents=True, exist_ok=True)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


for rel in ("showcase/basics.py", "showcase/vectors.py"):
    path = ROOT / "examples" / rel
    scene = _load_scene(str(path), None)
    ir = scene_to_ir(
        scene,
        sample_transform_functions=True,
        sample_dynamic_providers=True,
        sample_fps=scene.fps,
    )
    target = OUT / "ir" / f"{path.parent.name}_{path.stem}.zanim.json"
    target.write_text(json.dumps(ir, separators=(",", ":")), encoding="utf-8")
    print(target.relative_to(ROOT), target.stat().st_size)

fourier = load(ROOT / "examples/extras/fourier_draw.py", "gallery_fourier")
doc = fourier.load_svg(fourier.SVG)
contour = fourier.select_closed_contour(doc, strategy="longest")
samples = fourier.contour_samples(contour, fourier.SAMPLE_COUNT, tolerance=7e-4)
terms = fourier.dominant_terms(fourier.dft(samples), fourier.TERM_COUNT, keep_dc_first=True)
fourier_data = {
    "terms": [
        [int(term.frequency), float(term.coefficient.real), float(term.coefficient.imag)]
        for term in terms
    ],
    "reference": [[float(z.real), float(z.imag)] for z in samples]
    + [[float(samples[0].real), float(samples[0].imag)]],
    "start": fourier.START,
    "drawDuration": fourier.DRAW_DURATION,
    "hold": fourier.HOLD,
    "circleSamples": fourier.CIRCLE_SAMPLES,
    "traceSamples": fourier.TRACE_SAMPLES,
}

midi = load(ROOT / "examples/extras/midi_piano.py", "gallery_midi")
song = midi.parse_midi(midi.DEFAULT_MIDI)
midi_data = {
    "notes": [[n.pitch, n.velocity, n.start, n.end, n.channel] for n in song.notes],
    "duration": song.duration,
    "leadTime": midi.LEAD_TIME,
    "outro": midi.OUTRO,
    "trackName": song.track_name,
    "low": min(n.pitch for n in song.notes),
    "high": max(n.pitch for n in song.notes),
}

mnist = load(ROOT / "examples/extras/mnist_training.py", "gallery_mnist")
result = mnist._prepare_training_result(verbose=False)
trace = result.trace
mnist_data = {
    "meanLoss": [float(x) for x in trace.mean_loss],
    "trainAccuracy": [float(x) for x in trace.train_accuracy],
    "testAccuracy": [float(x) for x in trace.test_accuracy],
    "gradNormG1": [float(np.linalg.norm(x)) for x in trace.G1],
    "gradNormG2": [float(np.linalg.norm(x)) for x in trace.G2],
    "samples": [[round(float(v), 4) for v in row] for row in trace.samples],
    "sampleLabels": [int(x) for x in trace.sample_labels],
    "inference": [
        {
            "pixels": [round(float(v), 4) for v in result.inference.X[i]],
            "true": int(result.inference.y[i]),
            "pred": int(result.inference.pred[i]),
            "probs": [round(float(v), 6) for v in result.inference.probs[i]],
        }
        for i in range(len(result.inference.y))
    ],
    "introEnd": mnist.INTRO_END,
    "epochDuration": mnist.EPOCH_DURATION,
    "trainEnd": mnist.TRAIN_END,
    "inferenceEnd": mnist.INFERENCE_END,
    "finalEnd": mnist.FINAL_END,
    "forwardEnd": mnist.FORWARD_LOCAL_END,
    "backwardEnd": mnist.BACKWARD_LOCAL_END,
    "stackEnd": mnist.STACK_LOCAL_END,
    "updateEnd": mnist.UPDATE_LOCAL_END,
}

runtime = OUT / "python_reference_data.js"
runtime.write_text(
    "// Generated from canonical Python examples.\n"
    + "export const FOURIER_REFERENCE="
    + json.dumps(fourier_data, separators=(",", ":"))
    + ";\nexport const MIDI_REFERENCE="
    + json.dumps(midi_data, separators=(",", ":"))
    + ";\nexport const MNIST_REFERENCE="
    + json.dumps(mnist_data, separators=(",", ":"))
    + ";\n",
    encoding="utf-8",
)
print(runtime.relative_to(ROOT), runtime.stat().st_size)
