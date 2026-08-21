"""A readable, real MNIST training animation driven by epoch-level state.

The NumPy MLP is trained inside this script.  Zanim does not replay 7,504
mini-batch gradients: each epoch stores its exact start/end parameters, and the
visualized accumulated gradient is

    G_e = sum_b grad L_b = (W_e - W_{e+1}) / learning_rate.

That identity is exact for the constant-learning-rate SGD loop below.  The
animation remains absolute-time/random-access: any frame can be evaluated in
any order from the immutable epoch trace.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from math import ceil, floor
from pathlib import Path
import struct
from time import perf_counter
from functools import lru_cache

import numpy as np

from zanim import (
    BatchObject2D, Canvas, CircleSet, Color, Column, DynamicBatchObject2D,
    DynamicGeometryObject2D, DynamicNumber, Group2D,
    LineSet, Math, NumberFormat, Object2D, Polyline, RectSet, Rectangle,
    Scene, Style, Text, TOP, BOTTOM, Transform2D, Vec2, affine2d,
)

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "assets/MNIST/raw"
OUTPUT = ROOT / "media/fun/mnist_training.mp4"
BENCHMARK = ROOT / "media/fun/mnist_training_benchmark.json"

TRAIN_IMG = RAW / "train-images-idx3-ubyte"
TRAIN_LBL = RAW / "train-labels-idx1-ubyte"
TEST_IMG = RAW / "t10k-images-idx3-ubyte"
TEST_LBL = RAW / "t10k-labels-idx1-ubyte"

INPUT_SIZE = 784
HIDDEN_SIZE = 8
OUTPUT_SIZE = 10
EPOCHS = 8
BATCH_SIZE = 64
LEARNING_RATE = 0.1
SEED = 20260822
BATCHES_PER_EPOCH = ceil(60000 / BATCH_SIZE)

INTRO_END = 2.5
EPOCH_DURATION = 5.0
FORWARD_LOCAL_END = 1.55
BACKWARD_LOCAL_END = 3.10
STACK_LOCAL_END = 3.62
UPDATE_LOCAL_END = 4.40
TRAIN_END = INTRO_END + EPOCHS * EPOCH_DURATION
INFERENCE_END = TRAIN_END + 8.0
FINAL_END = INFERENCE_END + 2.0

WHITE = Color(237, 242, 250)
MUTED = Color(143, 157, 184)
BLUE = Color(83, 146, 255)
CYAN = Color(95, 218, 255)
GREEN = Color(87, 220, 159)
ORANGE = Color(255, 164, 82)
RED = Color(247, 93, 118)
PURPLE = Color(184, 124, 255)
YELLOW = Color(255, 221, 105)
PANEL = Color(90, 105, 132, 110)


def load_images(file: str | Path) -> np.ndarray:
    with open(file, "rb") as f:
        magic, size = struct.unpack(">ii", f.read(8))
        rows, cols = struct.unpack(">ii", f.read(8))
        if magic != 2051:
            raise ValueError(f"invalid MNIST image magic {magic}")
        images = np.fromfile(f, dtype=np.uint8).reshape((size, rows * cols))
    return images.astype(np.float64) / 255.0


def load_labels(file: str | Path) -> np.ndarray:
    with open(file, "rb") as f:
        magic, size = struct.unpack(">ii", f.read(8))
        if magic != 2049:
            raise ValueError(f"invalid MNIST label magic {magic}")
        labels = np.fromfile(f, dtype=np.uint8)
    if labels.shape != (size,):
        raise ValueError("MNIST label count mismatch")
    return labels


class MLP:
    def __init__(
        self,
        input_size: int,
        hidden_size: int,
        output_size: int,
        learning_rate: float = 0.1,
        *,
        seed: int = SEED,
    ) -> None:
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.output_size = output_size
        self.learning_rate = learning_rate

        rng = np.random.RandomState(seed)
        self.W1 = rng.randn(input_size, hidden_size) * 0.01
        self.b1 = np.zeros((1, hidden_size))
        self.W2 = rng.randn(hidden_size, output_size) * 0.01
        self.b2 = np.zeros((1, output_size))

        self.dW1 = np.zeros_like(self.W1)
        self.db1 = np.zeros_like(self.b1)
        self.dW2 = np.zeros_like(self.W2)
        self.db2 = np.zeros_like(self.b2)

    @staticmethod
    def sigmoid(z: np.ndarray) -> np.ndarray:
        return 1 / (1 + np.exp(-z))

    @staticmethod
    def sigmoid_derivative(z: np.ndarray) -> np.ndarray:
        s = 1 / (1 + np.exp(-z))
        return s * (1 - s)

    @staticmethod
    def softmax(z: np.ndarray) -> np.ndarray:
        exp_z = np.exp(z - np.max(z, axis=1, keepdims=True))
        return exp_z / np.sum(exp_z, axis=1, keepdims=True)

    def forward(self, X: np.ndarray) -> np.ndarray:
        self.Z1 = X @ self.W1 + self.b1
        self.Y1 = self.sigmoid(self.Z1)
        self.Z2 = self.Y1 @ self.W2 + self.b2
        self.Y2 = self.softmax(self.Z2)
        return self.Y2

    def compute_loss(self, y: np.ndarray) -> float:
        m = y.shape[0]
        eps = 1e-12
        log_probs = -np.log(self.Y2[np.arange(m), y] + eps)
        return float(np.sum(log_probs) / m)

    def backward(self, X: np.ndarray, y: np.ndarray) -> None:
        m = X.shape[0]
        y_onehot = np.zeros_like(self.Y2)
        y_onehot[np.arange(m), y] = 1.0

        dZ2 = self.Y2 - y_onehot
        self.dW2 = self.Y1.T @ dZ2 / m
        self.db2 = np.sum(dZ2, axis=0, keepdims=True) / m

        dY1 = dZ2 @ self.W2.T
        dZ1 = dY1 * self.sigmoid_derivative(self.Z1)
        self.dW1 = X.T @ dZ1 / m
        self.db1 = np.sum(dZ1, axis=0, keepdims=True) / m

    def step(self) -> None:
        self.W1 -= self.learning_rate * self.dW1
        self.b1 -= self.learning_rate * self.db1
        self.W2 -= self.learning_rate * self.dW2
        self.b2 -= self.learning_rate * self.db2

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.argmax(self.forward(X), axis=1)

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> float:
        return float(np.mean(self.predict(X) == y))

    def save_model(self, path: str | Path) -> None:
        np.savez(path, W1=self.W1, b1=self.b1, W2=self.W2, b2=self.b2)


@dataclass(frozen=True, slots=True)
class EpochTrace:
    W1: np.ndarray             # [9, 784, 8], epoch boundaries
    b1: np.ndarray             # [9, 8]
    W2: np.ndarray             # [9, 8, 10]
    b2: np.ndarray             # [9, 10]
    G1: np.ndarray             # [8, 784, 8], sum of all batch dW1 in epoch
    Gb1: np.ndarray            # [8, 8]
    G2: np.ndarray             # [8, 8, 10]
    Gb2: np.ndarray            # [8, 10]
    mean_loss: np.ndarray      # [8]
    train_accuracy: np.ndarray # [8]
    test_accuracy: np.ndarray  # [8]
    samples: np.ndarray        # [8, 784], representative real samples
    sample_labels: np.ndarray  # [8]

    @property
    def memory_bytes(self) -> int:
        arrays = (
            self.W1, self.b1, self.W2, self.b2,
            self.G1, self.Gb1, self.G2, self.Gb2,
            self.mean_loss, self.train_accuracy, self.test_accuracy,
            self.samples, self.sample_labels,
        )
        return int(sum(array.nbytes for array in arrays))


@dataclass(frozen=True, slots=True)
class InferenceSet:
    X: np.ndarray
    y: np.ndarray
    pred: np.ndarray
    probs: np.ndarray
    source_indices: np.ndarray


@dataclass(frozen=True, slots=True)
class TrainingResult:
    model: MLP
    trace: EpochTrace
    inference: InferenceSet
    train_seconds: float
    final_train_accuracy: float
    final_test_accuracy: float


def train_with_epoch_trace(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    *,
    epochs: int = EPOCHS,
    batch_size: int = BATCH_SIZE,
    learning_rate: float = LEARNING_RATE,
) -> TrainingResult:
    mlp = MLP(INPUT_SIZE, HIDDEN_SIZE, OUTPUT_SIZE, learning_rate)

    W1 = np.empty((epochs + 1, INPUT_SIZE, HIDDEN_SIZE), dtype=np.float32)
    b1 = np.empty((epochs + 1, HIDDEN_SIZE), dtype=np.float32)
    W2 = np.empty((epochs + 1, HIDDEN_SIZE, OUTPUT_SIZE), dtype=np.float32)
    b2 = np.empty((epochs + 1, OUTPUT_SIZE), dtype=np.float32)
    G1 = np.empty((epochs, INPUT_SIZE, HIDDEN_SIZE), dtype=np.float32)
    Gb1 = np.empty((epochs, HIDDEN_SIZE), dtype=np.float32)
    G2 = np.empty((epochs, HIDDEN_SIZE, OUTPUT_SIZE), dtype=np.float32)
    Gb2 = np.empty((epochs, OUTPUT_SIZE), dtype=np.float32)
    mean_loss = np.empty(epochs, dtype=np.float32)
    train_accuracy = np.empty(epochs, dtype=np.float32)
    test_accuracy = np.empty(epochs, dtype=np.float32)

    W1[0], b1[0], W2[0], b2[0] = mlp.W1, mlp.b1, mlp.W2, mlp.b2

    # Eight visually distinct real MNIST examples, one per epoch.
    sample_indices = np.asarray([
        int(np.flatnonzero(y_train == digit)[0]) for digit in range(epochs)
    ])
    samples = X_train[sample_indices].astype(np.float32, copy=True)
    sample_labels = y_train[sample_indices].astype(np.int16, copy=True)

    started = perf_counter()
    for epoch in range(epochs):
        sum_dW1 = np.zeros_like(mlp.W1)
        sum_db1 = np.zeros_like(mlp.b1)
        sum_dW2 = np.zeros_like(mlp.W2)
        sum_db2 = np.zeros_like(mlp.b2)
        losses: list[float] = []

        for i in range(0, X_train.shape[0], batch_size):
            Xb = X_train[i:i + batch_size]
            yb = y_train[i:i + batch_size]
            mlp.forward(Xb)
            losses.append(mlp.compute_loss(yb))
            mlp.backward(Xb, yb)

            sum_dW1 += mlp.dW1
            sum_db1 += mlp.db1
            sum_dW2 += mlp.dW2
            sum_db2 += mlp.db2
            mlp.step()

        W1[epoch + 1], b1[epoch + 1] = mlp.W1, mlp.b1
        W2[epoch + 1], b2[epoch + 1] = mlp.W2, mlp.b2

        # Constant eta makes this exact even though each mini-batch gradient was
        # evaluated at a different intermediate parameter state.
        effective_G1 = (W1[epoch].astype(np.float64) - W1[epoch + 1]) / learning_rate
        effective_Gb1 = (b1[epoch].astype(np.float64) - b1[epoch + 1]) / learning_rate
        effective_G2 = (W2[epoch].astype(np.float64) - W2[epoch + 1]) / learning_rate
        effective_Gb2 = (b2[epoch].astype(np.float64) - b2[epoch + 1]) / learning_rate
        np.testing.assert_allclose(effective_G1, sum_dW1, rtol=2e-5, atol=2e-5)
        np.testing.assert_allclose(effective_Gb1, sum_db1.reshape(-1), rtol=2e-5, atol=2e-5)
        np.testing.assert_allclose(effective_G2, sum_dW2, rtol=2e-5, atol=2e-5)
        np.testing.assert_allclose(effective_Gb2, sum_db2.reshape(-1), rtol=2e-5, atol=2e-5)
        G1[epoch], Gb1[epoch] = effective_G1, effective_Gb1
        G2[epoch], Gb2[epoch] = effective_G2, effective_Gb2

        mean_loss[epoch] = float(np.mean(losses))
        train_accuracy[epoch] = mlp.evaluate(X_train, y_train)
        test_accuracy[epoch] = mlp.evaluate(X_test, y_test)
        print(
            f"[Epoch {epoch + 1}/{epochs}] mean_loss={mean_loss[epoch]:.4f} "
            f"Train={train_accuracy[epoch]:.4f} Test={test_accuracy[epoch]:.4f}"
        )

    train_seconds = perf_counter() - started
    final_probs = mlp.forward(X_test).copy()
    final_pred = np.argmax(final_probs, axis=1)
    final_train_accuracy = mlp.evaluate(X_train, y_train)
    final_test_accuracy = float(np.mean(final_pred == y_test))

    correct = np.flatnonzero(final_pred == y_test)
    wrong = np.flatnonzero(final_pred != y_test)
    confidence = np.max(final_probs, axis=1)
    choices = [
        int(correct[np.argmax(confidence[correct])]),
        int(correct[np.argsort(confidence[correct])[len(correct) // 2]]),
        int(wrong[np.argmax(confidence[wrong])]),
        int(wrong[np.argmin(confidence[wrong])]),
    ]
    idx = np.asarray(choices, dtype=np.int64)

    return TrainingResult(
        model=mlp,
        trace=EpochTrace(
            W1=W1, b1=b1, W2=W2, b2=b2,
            G1=G1, Gb1=Gb1, G2=G2, Gb2=Gb2,
            mean_loss=mean_loss,
            train_accuracy=train_accuracy,
            test_accuracy=test_accuracy,
            samples=samples,
            sample_labels=sample_labels,
        ),
        inference=InferenceSet(
            X=X_test[idx].astype(np.float32, copy=True),
            y=y_test[idx].astype(np.int16, copy=True),
            pred=final_pred[idx].astype(np.int16, copy=True),
            probs=final_probs[idx].astype(np.float32, copy=True),
            source_indices=idx,
        ),
        train_seconds=train_seconds,
        final_train_accuracy=final_train_accuracy,
        final_test_accuracy=final_test_accuracy,
    )


def _smooth01(value: float) -> float:
    x = max(0.0, min(1.0, float(value)))
    return x * x * (3.0 - 2.0 * x)


def _input_centers() -> tuple[Vec2, ...]:
    center = Vec2(-7.0, 0.55)
    spacing = 0.083
    half = 13.5 * spacing
    return tuple(
        Vec2(center.x + col * spacing - half, center.y + half - row * spacing)
        for row in range(28)
        for col in range(28)
    )


def _filter_centers() -> tuple[Vec2, ...]:
    return tuple(
        Vec2(-4.22 + 0.88 * col, 1.70 - 0.86 * row)
        for row in range(4)
        for col in range(2)
    )


FILTER_CLUSTER_CENTER = Vec2(-3.78, 0.41)
WEIGHT_SLOT_CENTER = Vec2(-4.75, 2.52)
GRADIENT_SLOT_CENTER = Vec2(-3.25, 2.52)
UPDATE_SCALE = 0.43


def _slot_transform(target: Vec2) -> Transform2D:
    """Shrink the W1 tile cluster around its own center and place it in a slot."""
    return (
        Transform2D.translation(target.x, target.y)
        @ Transform2D.scaling(UPDATE_SCALE)
        @ Transform2D.translation(-FILTER_CLUSTER_CENTER.x, -FILTER_CLUSTER_CENTER.y)
    )


WEIGHT_SLOT_TRANSFORM = _slot_transform(WEIGHT_SLOT_CENTER)
GRADIENT_SLOT_TRANSFORM = _slot_transform(GRADIENT_SLOT_CENTER)


def _filter_cells() -> tuple[Vec2, ...]:
    cells: list[Vec2] = []
    spacing = 0.022
    half = 13.5 * spacing
    for center in _filter_centers():
        cells.extend(
            Vec2(center.x + col * spacing - half, center.y + half - row * spacing)
            for row in range(28)
            for col in range(28)
        )
    return tuple(cells)


def _layer_centers(x: float, count: int, height: float) -> tuple[Vec2, ...]:
    return tuple(
        Vec2(x, 0.35 + height * (0.5 - i / (count - 1)))
        for i in range(count)
    )


class EpochVisual:
    def __init__(self, trace: EpochTrace, inference: InferenceSet) -> None:
        self.trace = trace
        self.inference = inference
        self.input_centers = _input_centers()
        self.filter_centers = _filter_centers()
        self.filter_cells = _filter_cells()
        self.hidden_centers = _layer_centers(-1.55, HIDDEN_SIZE, 3.65)
        self.output_centers = _layer_centers(1.15, OUTPUT_SIZE, 4.15)
        self.w2_starts = tuple(p for p in self.hidden_centers for _ in self.output_centers)
        self.w2_ends = tuple(p for _ in self.hidden_centers for p in self.output_centers)

        # Eight readable aggregate paths stand in front of the dense W1 maps.
        # They communicate propagation direction without reintroducing 6,272
        # crossing lines; the maps themselves still display every W1 weight.
        input_edge = Vec2(-5.73, 0.55)
        self.input_filter_starts = (input_edge,) * HIDDEN_SIZE
        self.input_filter_ends = self.filter_centers
        self.filter_hidden_starts = self.filter_centers
        self.filter_hidden_ends = self.hidden_centers

    def epoch_local(self, time: float) -> tuple[int, float]:
        if time < INTRO_END:
            return 0, 0.0
        if time >= TRAIN_END:
            return EPOCHS - 1, EPOCH_DURATION
        pos = (time - INTRO_END) / EPOCH_DURATION
        epoch = max(0, min(EPOCHS - 1, int(floor(pos))))
        return epoch, (pos - epoch) * EPOCH_DURATION

    def inference_index(self, time: float) -> int:
        if time < TRAIN_END:
            return 0
        u = max(0.0, min(0.999999, (time - TRAIN_END) / (INFERENCE_END - TRAIN_END)))
        return min(len(self.inference.y) - 1, int(u * len(self.inference.y)))

    def display_epoch(self, time: float) -> int:
        if time < INTRO_END:
            return 1
        if time >= TRAIN_END:
            return EPOCHS
        epoch, _ = self.epoch_local(time)
        return epoch + 1

    def completed_epochs(self, time: float) -> int:
        if time < INTRO_END:
            return 0
        if time >= TRAIN_END:
            return EPOCHS
        epoch, local = self.epoch_local(time)
        return epoch + (1 if local >= UPDATE_LOCAL_END else 0)

    @lru_cache(maxsize=32)
    def _boundary_weights(self, index: int):
        return (
            self.trace.W1[index], self.trace.b1[index],
            self.trace.W2[index], self.trace.b2[index],
        )

    def weights_at(self, time: float):
        if time < INTRO_END:
            return self._boundary_weights(0)
        if time >= TRAIN_END:
            return self._boundary_weights(EPOCHS)
        epoch, local = self.epoch_local(time)
        if local < STACK_LOCAL_END:
            return self._boundary_weights(epoch)
        if local >= UPDATE_LOCAL_END:
            return self._boundary_weights(epoch + 1)
        a = _smooth01((local - STACK_LOCAL_END) / (UPDATE_LOCAL_END - STACK_LOCAL_END))
        before = self._boundary_weights(epoch)
        after = self._boundary_weights(epoch + 1)
        return tuple(x * (1 - a) + y * a for x, y in zip(before, after))

    def sample_at(self, time: float) -> tuple[np.ndarray, int]:
        if time >= TRAIN_END:
            i = self.inference_index(time)
            return self.inference.X[i], int(self.inference.y[i])
        epoch, _ = self.epoch_local(time)
        return self.trace.samples[epoch], int(self.trace.sample_labels[epoch])

    @lru_cache(maxsize=64)
    def sample_state(self, time: float):
        x, label = self.sample_at(time)
        W1, b1, W2, b2 = self.weights_at(time)
        z1 = x @ W1 + b1
        y1 = 1.0 / (1.0 + np.exp(-z1))
        z2 = y1 @ W2 + b2
        exp_z = np.exp(z2 - np.max(z2))
        y2 = exp_z / np.sum(exp_z)
        pred = int(np.argmax(y2))
        conf = float(y2[pred])
        return x, y1, y2, label, pred, conf

    def _inference_local(self, time: float) -> float:
        if time < TRAIN_END:
            return 0.0
        segment = max(0.0, time - TRAIN_END) % 2.0
        return min(FORWARD_LOCAL_END, segment)

    def _forward_local(self, time: float) -> float | None:
        if INTRO_END <= time < TRAIN_END:
            _, local = self.epoch_local(time)
            return local if local < FORWARD_LOCAL_END else None
        if TRAIN_END <= time < INFERENCE_END:
            return self._inference_local(time)
        return None

    @staticmethod
    def _staggered(progress: float, index: int, count: int, *, spread: float = 0.46) -> float:
        if count <= 1:
            return _smooth01(progress)
        offset = spread * index / (count - 1)
        return _smooth01((progress - offset) / max(1e-9, 1.0 - spread))

    @staticmethod
    def _lerp_point(a: Vec2, b: Vec2, alpha: float) -> Vec2:
        return Vec2(a.x + (b.x - a.x) * alpha, a.y + (b.y - a.y) * alpha)

    @staticmethod
    def _scaled_alpha(color: Color, scale: float) -> Color:
        return color.with_alpha(max(0, min(255, round(color.a * max(0.0, min(1.0, scale))))))

    def input_reveal(self, time: float) -> float:
        local = self._forward_local(time)
        if local is None:
            return 1.0
        return _smooth01((local - 0.02) / 0.24)

    def result_reveal(self, time: float) -> float:
        """Hide prediction/probability until the forward wave reaches output."""
        if time < INTRO_END:
            return 0.0
        if INTRO_END <= time < TRAIN_END:
            _, local = self.epoch_local(time)
            if local < FORWARD_LOCAL_END:
                return _smooth01((local - 1.02) / 0.42)
            if local < UPDATE_LOCAL_END:
                return 1.0
            return 0.0
        if TRAIN_END <= time < INFERENCE_END:
            local = self._inference_local(time)
            return _smooth01((local - 1.02) / 0.42)
        return 0.0

    def forward_stage(self, time: float) -> tuple[float, float, float, float]:
        local = self._forward_local(time)
        if local is None:
            return (0.0, 0.0, 0.0, 0.0)
        input_to_filter = _smooth01((local - 0.12) / 0.38)
        filter_to_hidden = _smooth01((local - 0.36) / 0.46)
        hidden_to_output = _smooth01((local - 0.70) / 0.55)
        output_light = _smooth01((local - 1.02) / 0.42)
        return input_to_filter, filter_to_hidden, hidden_to_output, output_light

    def backward_stage(self, time: float) -> tuple[float, float, float]:
        if not (INTRO_END <= time < TRAIN_END):
            return (0.0, 0.0, 0.0)
        _, local = self.epoch_local(time)
        if not (FORWARD_LOCAL_END <= local < BACKWARD_LOCAL_END):
            return (0.0, 0.0, 0.0)
        u = local - FORWARD_LOCAL_END
        output_to_hidden = _smooth01((u - 0.08) / 0.48)
        hidden_to_filter = _smooth01((u - 0.46) / 0.48)
        filter_to_input = _smooth01((u - 0.86) / 0.48)
        return output_to_hidden, hidden_to_filter, filter_to_input

    def node_phase(self, time: float, *, layer: str, index: int, count: int) -> tuple[float, bool]:
        forward = self._forward_local(time)
        if forward is not None:
            if layer == "hidden":
                base = (forward - 0.42) / 0.56
            else:
                base = (forward - 0.98) / 0.46
            return self._staggered(base, index, count, spread=0.42), False

        if INTRO_END <= time < TRAIN_END:
            _, local = self.epoch_local(time)
            if FORWARD_LOCAL_END <= local < BACKWARD_LOCAL_END:
                u = local - FORWARD_LOCAL_END
                if layer == "output":
                    base = (u - 0.02) / 0.54
                    # Error signals originate at the output layer.
                    order = count - 1 - index
                else:
                    base = (u - 0.48) / 0.54
                    order = count - 1 - index
                return self._staggered(base, order, count, spread=0.42), True
        return 0.18, False

    def _grown_lines(
        self, starts: tuple[Vec2, ...], ends: tuple[Vec2, ...],
        colors: tuple[Color, ...], widths: tuple[float, ...], progress: float,
        *, reverse: bool = False, groups: int | None = None, group_size: int = 1,
    ) -> LineSet:
        source = ends if reverse else starts
        target = starts if reverse else ends
        grown_ends: list[Vec2] = []
        grown_colors: list[Color] = []
        for i, (a, b, color) in enumerate(zip(source, target, colors)):
            if groups is None:
                p = _smooth01(progress)
            else:
                group = min(groups - 1, i // max(1, group_size))
                p = self._staggered(progress, group, groups, spread=0.48)
            grown_ends.append(self._lerp_point(a, b, p))
            grown_colors.append(self._scaled_alpha(color, p))
        return LineSet(source, tuple(grown_ends), tuple(grown_colors), widths)

    @staticmethod
    def _signed_colors(values: np.ndarray, positive: Color, negative: Color, *, min_alpha=18):
        flat = np.asarray(values, dtype=np.float64).reshape(-1)
        scale = max(1e-12, float(np.max(np.abs(flat))))
        mags = np.minimum(1.0, np.abs(flat) / scale)
        return tuple(
            (positive if value >= 0 else negative).with_alpha(
                int(round(min_alpha + (235 - min_alpha) * mag))
            )
            for value, mag in zip(flat, mags)
        ), mags

    @lru_cache(maxsize=9)
    def _static_weight_filters(self, boundary: int) -> RectSet:
        # Flatten by hidden neuron so each 28x28 tile is one complete W1 column.
        values = self.trace.W1[boundary].T.reshape(-1)
        colors, _ = self._signed_colors(values, BLUE, RED, min_alpha=28)
        return RectSet(
            self.filter_cells,
            (Vec2(0.0205, 0.0205),) * len(self.filter_cells),
            colors,
        )

    def weight_filters(self, time: float) -> RectSet:
        if time < INTRO_END:
            return self._static_weight_filters(0)
        if time >= TRAIN_END:
            return self._static_weight_filters(EPOCHS)
        epoch, local = self.epoch_local(time)
        if local < BACKWARD_LOCAL_END:
            return self._static_weight_filters(epoch)
        if local >= UPDATE_LOCAL_END:
            return self._static_weight_filters(epoch + 1)
        W1, *_ = self.weights_at(time)
        values = W1.T.reshape(-1)
        colors, _ = self._signed_colors(values, BLUE, RED, min_alpha=28)
        return RectSet(
            self.filter_cells,
            (Vec2(0.0205, 0.0205),) * len(self.filter_cells),
            colors,
        )

    @lru_cache(maxsize=8)
    def _gradient_filters(self, epoch: int) -> RectSet:
        values = self.trace.G1[epoch].T.reshape(-1)
        colors, _ = self._signed_colors(values, PURPLE, ORANGE, min_alpha=12)
        return RectSet(
            self.filter_cells,
            (Vec2(0.0205, 0.0205),) * len(self.filter_cells),
            colors,
        )

    @lru_cache(maxsize=64)
    def _gradient_filter_tile(self, epoch: int, hidden_index: int) -> RectSet:
        base = self._gradient_filters(epoch)
        start = hidden_index * INPUT_SIZE
        end = start + INPUT_SIZE
        return RectSet(
            base.centers[start:end],
            base.sizes[start:end],
            base.fills[start:end],
        )

    @lru_cache(maxsize=8)
    def _hidden_gradient_filters(self, epoch: int) -> RectSet:
        base = self._gradient_filters(epoch)
        return RectSet(
            base.centers, base.sizes,
            tuple(color.with_alpha(0) for color in base.fills),
        )

    def gradient_filters(self, time: float) -> RectSet:
        epoch, local = self.epoch_local(time)
        base = self._gradient_filters(epoch)
        _, hidden_to_filter, filter_to_input = self.backward_stage(time)
        reveal = max(hidden_to_filter, filter_to_input)
        if BACKWARD_LOCAL_END <= local < UPDATE_LOCAL_END:
            reveal = 1.0
        if reveal <= 1e-12:
            return self._hidden_gradient_filters(epoch)
        if reveal >= 1.0 - 1e-12:
            return base
        fills: list[Color] = []
        for i, color in enumerate(base.fills):
            filter_index = i // INPUT_SIZE
            p = self._staggered(reveal, HIDDEN_SIZE - 1 - filter_index, HIDDEN_SIZE, spread=0.42)
            fills.append(self._scaled_alpha(color, p))
        return RectSet(base.centers, base.sizes, tuple(fills))

    @lru_cache(maxsize=9)
    def _static_w2_lines(self, boundary: int) -> LineSet:
        values = self.trace.W2[boundary].reshape(-1)
        colors, mags = self._signed_colors(values, BLUE, RED, min_alpha=20)
        widths = tuple(float(0.004 + 0.014 * mag) for mag in mags)
        return LineSet(self.w2_starts, self.w2_ends, colors, widths)

    def w2_lines(self, time: float) -> LineSet:
        if time < INTRO_END:
            return self._static_w2_lines(0)
        if time >= TRAIN_END:
            return self._static_w2_lines(EPOCHS)
        epoch, local = self.epoch_local(time)
        if local < BACKWARD_LOCAL_END:
            return self._static_w2_lines(epoch)
        if local >= UPDATE_LOCAL_END:
            return self._static_w2_lines(epoch + 1)
        *_, W2, _ = self.weights_at(time)
        values = W2.reshape(-1)
        colors, mags = self._signed_colors(values, BLUE, RED, min_alpha=20)
        widths = tuple(float(0.004 + 0.014 * mag) for mag in mags)
        return LineSet(self.w2_starts, self.w2_ends, colors, widths)

    @lru_cache(maxsize=8)
    def _gradient_w2_lines(self, epoch: int) -> LineSet:
        values = self.trace.G2[epoch].reshape(-1)
        colors, mags = self._signed_colors(values, PURPLE, ORANGE, min_alpha=18)
        widths = tuple(float(0.006 + 0.020 * mag) for mag in mags)
        return LineSet(self.w2_starts, self.w2_ends, colors, widths)

    def gradient_w2_lines(self, time: float) -> LineSet:
        epoch, _ = self.epoch_local(time)
        return self._gradient_w2_lines(epoch)

    def forward_input_filter_lines(self, time: float) -> LineSet:
        progress, _, _, _ = self.forward_stage(time)
        colors = (CYAN.with_alpha(150),) * HIDDEN_SIZE
        widths = (0.012,) * HIDDEN_SIZE
        return self._grown_lines(
            self.input_filter_starts, self.input_filter_ends, colors, widths,
            progress, groups=HIDDEN_SIZE,
        )

    def forward_filter_hidden_lines(self, time: float) -> LineSet:
        _, progress, _, _ = self.forward_stage(time)
        colors = (CYAN.with_alpha(180),) * HIDDEN_SIZE
        widths = (0.014,) * HIDDEN_SIZE
        return self._grown_lines(
            self.filter_hidden_starts, self.filter_hidden_ends, colors, widths,
            progress, groups=HIDDEN_SIZE,
        )

    def forward_w2_lines(self, time: float) -> LineSet:
        _, _, progress, _ = self.forward_stage(time)
        if time >= TRAIN_END:
            boundary = EPOCHS
        elif time < INTRO_END:
            boundary = 0
        else:
            epoch, _ = self.epoch_local(time)
            boundary = epoch
        base = self._static_w2_lines(boundary)
        return self._grown_lines(
            base.starts, base.ends, base.colors, base.widths, progress,
            groups=HIDDEN_SIZE, group_size=OUTPUT_SIZE,
        )

    def backward_w2_lines(self, time: float) -> LineSet:
        epoch, _ = self.epoch_local(time)
        progress, _, _ = self.backward_stage(time)
        base = self._gradient_w2_lines(epoch)

        # W2 is stored hidden-major. Reorder it output-major so each output
        # neuron's error fan grows back toward all eight hidden neurons together.
        starts: list[Vec2] = []
        ends: list[Vec2] = []
        colors: list[Color] = []
        widths: list[float] = []
        for output_index in range(OUTPUT_SIZE):
            for hidden_index in range(HIDDEN_SIZE):
                i = hidden_index * OUTPUT_SIZE + output_index
                starts.append(base.ends[i])
                ends.append(base.starts[i])
                colors.append(base.colors[i])
                widths.append(base.widths[i])
        return self._grown_lines(
            tuple(starts), tuple(ends), tuple(colors), tuple(widths), progress,
            groups=OUTPUT_SIZE, group_size=HIDDEN_SIZE,
        )

    def backward_hidden_filter_lines(self, time: float) -> LineSet:
        epoch, _ = self.epoch_local(time)
        _, progress, _ = self.backward_stage(time)
        g = np.linalg.norm(self.trace.G1[epoch], axis=0)
        scale = max(1e-12, float(np.max(g)))
        colors = tuple(PURPLE.with_alpha(round(55 + 190 * float(v / scale))) for v in g)
        widths = tuple(0.012 + 0.014 * float(v / scale) for v in g)
        return self._grown_lines(
            self.filter_hidden_starts, self.filter_hidden_ends, colors, widths,
            progress, reverse=True, groups=HIDDEN_SIZE,
        )

    def backward_filter_input_lines(self, time: float) -> LineSet:
        epoch, _ = self.epoch_local(time)
        _, _, progress = self.backward_stage(time)
        g = np.linalg.norm(self.trace.G1[epoch], axis=0)
        scale = max(1e-12, float(np.max(g)))
        colors = tuple(ORANGE.with_alpha(round(45 + 185 * float(v / scale))) for v in g)
        widths = tuple(0.010 + 0.012 * float(v / scale) for v in g)
        return self._grown_lines(
            self.input_filter_starts, self.input_filter_ends, colors, widths,
            progress, reverse=True, groups=HIDDEN_SIZE,
        )

    @lru_cache(maxsize=12)
    def _input_for_key(self, key: int, inference: bool) -> RectSet:
        x = self.inference.X[key] if inference else self.trace.samples[key]
        fills = tuple(
            Color(round(20 + 230 * v), round(23 + 230 * v), round(31 + 220 * v))
            for v in x
        )
        return RectSet(
            self.input_centers,
            (Vec2(0.077, 0.077),) * INPUT_SIZE,
            fills,
        )

    def input_pixels(self, time: float) -> RectSet:
        if time >= TRAIN_END:
            base = self._input_for_key(self.inference_index(time), True)
        else:
            epoch, _ = self.epoch_local(time)
            base = self._input_for_key(epoch, False)
        reveal = self.input_reveal(time)
        if reveal >= 1.0 - 1e-12:
            return base
        fills = tuple(
            Color(
                round(16 + (color.r - 16) * reveal),
                round(18 + (color.g - 18) * reveal),
                round(24 + (color.b - 24) * reveal),
                color.a,
            )
            for color in base.fills
        )
        return RectSet(base.centers, base.sizes, fills)

    def hidden_nodes(self, time: float) -> CircleSet:
        _, hidden, _, _, _, _ = self.sample_state(float(time))
        radii: list[float] = []
        fills: list[Color] = []
        strokes: list[Color] = []
        for i, value in enumerate(np.asarray(hidden)):
            light, backward = self.node_phase(time, layer="hidden", index=i, count=HIDDEN_SIZE)
            activation = float(value) * light
            base = PURPLE if backward else CYAN
            radii.append(0.105 + 0.11 * activation + 0.025 * light)
            fills.append(base.with_alpha(round(28 + 220 * max(light * 0.45, activation))))
            strokes.append((ORANGE if backward else WHITE).with_alpha(round(90 + 150 * light)))
        return CircleSet(
            self.hidden_centers, tuple(radii), tuple(fills),
            tuple(strokes), (0.016,) * HIDDEN_SIZE,
        )

    def output_nodes(self, time: float) -> CircleSet:
        _, _, probs, _, _, _ = self.sample_state(float(time))
        radii: list[float] = []
        fills: list[Color] = []
        strokes: list[Color] = []
        for i, value in enumerate(np.asarray(probs)):
            light, backward = self.node_phase(time, layer="output", index=i, count=OUTPUT_SIZE)
            activation = float(value) * light
            base = ORANGE if backward else GREEN
            radii.append(0.095 + 0.18 * activation + 0.024 * light)
            fills.append(base.with_alpha(round(26 + 225 * max(light * 0.42, activation))))
            strokes.append((PURPLE if backward else WHITE).with_alpha(round(85 + 155 * light)))
        return CircleSet(
            self.output_centers, tuple(radii), tuple(fills),
            tuple(strokes), (0.016,) * OUTPUT_SIZE,
        )

    def probability_bars(self, time: float) -> RectSet:
        _, _, probs, _, pred, _ = self.sample_state(float(time))
        reveal = self.result_reveal(time)
        centers: list[Vec2] = []
        sizes: list[Vec2] = []
        fills: list[Color] = []
        for digit, (node, probability) in enumerate(zip(self.output_centers, probs)):
            width = 0.02 + 1.05 * float(probability) * reveal
            centers.append(Vec2(1.62 + width * 0.5, node.y))
            sizes.append(Vec2(width, 0.095))
            fills.append(
                (YELLOW if digit == pred else GREEN).with_alpha(round(205 * reveal))
            )
        return RectSet(tuple(centers), tuple(sizes), tuple(fills))

    def mean_loss_at(self, time: float) -> float:
        epoch = self.display_epoch(time) - 1
        return float(self.trace.mean_loss[epoch])

    def train_acc_at(self, time: float) -> float:
        epoch = self.display_epoch(time) - 1
        return float(self.trace.train_accuracy[epoch] * 100)

    def test_acc_at(self, time: float) -> float:
        epoch = self.display_epoch(time) - 1
        return float(self.trace.test_accuracy[epoch] * 100)

    def grad_norm_g1(self, time: float) -> float:
        epoch = self.display_epoch(time) - 1
        return float(np.linalg.norm(self.trace.G1[epoch]))

    def grad_norm_g2(self, time: float) -> float:
        epoch = self.display_epoch(time) - 1
        return float(np.linalg.norm(self.trace.G2[epoch]))


def _dynamic_number(
    provider,
    *,
    at: tuple[float, float],
    color: Color = WHITE,
    width: int = 7,
    decimals: int = 3,
    font_size: int = 19,
    opacity: float = 1.0,
) -> DynamicNumber:
    return DynamicNumber(
        provider,
        number_format=NumberFormat(width=width, decimals=decimals, sign="space"),
        font_size=font_size,
        color=color,
        transform=affine2d(to=at),
        opacity=opacity,
        z_index=15,
    )


def _curve(points: tuple[Vec2, ...], count: int) -> Polyline:
    if count <= 0:
        return Polyline((points[0], points[0]))
    visible = points[:count]
    return Polyline(visible if len(visible) >= 2 else (visible[0], visible[0]))


def build_scene(result: TrainingResult) -> Scene:
    trace = result.trace
    visual = EpochVisual(trace, result.inference)
    scene = Scene(canvas=Canvas(1920, 1080, 105), fps=60)

    # Dense first-layer weights are shown as eight learned 28x28 filters instead
    # of 6,272 crossing lines. No weight is discarded.
    pixels = DynamicBatchObject2D(visual.input_pixels, z_index=3)
    # W1 has known epoch endpoints, so use the retained BatchClip channel.
    # The Zig renderer interpolates the two cached endpoint batches directly;
    # Python does not rebuild 6,272 colors on every update frame.
    weight_filters = BatchObject2D(visual._static_weight_filters(0), z_index=3)
    # G1 is also known per epoch. Keep eight static filter tiles so the backward
    # wave can reveal them independently without rebuilding 6,272 colors/frame.
    gradient_tile_objects = [
        BatchObject2D(visual._gradient_filter_tile(0, i), opacity=0, z_index=4)
        for i in range(HIDDEN_SIZE)
    ]
    gradient_filters = Group2D(gradient_tile_objects, z_index=4)
    hidden = DynamicBatchObject2D(visual.hidden_nodes, z_index=6)
    output = DynamicBatchObject2D(visual.output_nodes, z_index=6)
    bars = DynamicBatchObject2D(visual.probability_bars, z_index=4)

    # Propagation lines are transient absolute-time geometry. Each epoch starts
    # with a clean network, then forward lines grow left->right and accumulated
    # gradient lines grow right->left.
    f_input_filter = DynamicBatchObject2D(visual.forward_input_filter_lines, z_index=2)
    f_filter_hidden = DynamicBatchObject2D(visual.forward_filter_hidden_lines, z_index=2)
    f_w2 = DynamicBatchObject2D(visual.forward_w2_lines, z_index=2)
    b_w2 = DynamicBatchObject2D(visual.backward_w2_lines, z_index=3)
    b_hidden_filter = DynamicBatchObject2D(visual.backward_hidden_filter_lines, z_index=3)
    b_filter_input = DynamicBatchObject2D(visual.backward_filter_input_lines, z_index=3)

    title = Text("MNIST MLP · eight real training epochs", font_size=34, color=WHITE)
    subtitle = Text(
        "real NumPy training · each backward pass accumulates all 938 mini-batches",
        font_size=20, color=MUTED,
    )
    title.place(anchor=TOP, at=scene.frame.top + Vec2(0, -0.26))
    subtitle.place(anchor=TOP, at=title.anchor(BOTTOM) + Vec2(0, -0.10))

    input_label = Text("28 × 28 input", font_size=17, color=MUTED)
    filters_label = Text("W₁ · 8 learned filters", font_size=17, color=MUTED)
    hidden_label = Text("sigmoid · 8", font_size=17, color=MUTED)
    output_label = Text("softmax · 10", font_size=17, color=MUTED)
    input_label.place(anchor=BOTTOM, at=Vec2(-7.0, -1.02))
    filters_label.place(anchor=BOTTOM, at=Vec2(-3.78, -2.05))
    hidden_label.place(anchor=BOTTOM, at=Vec2(-1.55, -1.90))
    output_label.place(anchor=BOTTOM, at=Vec2(1.15, -2.15))

    filter_numbers = []
    for i, center in enumerate(visual.filter_centers):
        label = Text(f"h{i}", font_size=11, color=MUTED)
        label.place(anchor=BOTTOM, at=Vec2(center.x, center.y - 0.38))
        filter_numbers.append(label)

    digit_labels = []
    for digit, node in enumerate(visual.output_centers):
        label = Text(str(digit), font_size=14, color=MUTED)
        label.place(anchor=BOTTOM, at=Vec2(1.48, node.y - 0.05))
        digit_labels.append(label)

    # Right panel is exclusively metrics; formulas live in their own bottom strip.
    metrics_frame = Object2D(
        Rectangle(4.55, 3.25), position=(6.35, 1.40),
        stroke=PANEL, stroke_width=0.012, z_index=8,
    )
    metrics_title = Text("training state", font_size=17, color=MUTED)
    metrics_title.place(anchor=TOP, at=Vec2(6.35, 3.00))

    metric_specs = [
        ("epoch", 2.55),
        ("mean loss", 2.08),
        ("train acc %", 1.61),
        ("test acc %", 1.14),
        ("||G₁||₂", 0.67),
        ("||G₂||₂", 0.20),
    ]
    metric_labels = []
    for i, (text, y) in enumerate(metric_specs):
        item = Text(text, font_size=16, color=MUTED, opacity=1 if i == 0 else 0)
        item.place(anchor=TOP, at=Vec2(4.55, y))
        metric_labels.append(item)

    epoch_num = _dynamic_number(visual.display_epoch, at=(7.72, 2.48), color=CYAN, width=2, decimals=0)
    loss_num = _dynamic_number(visual.mean_loss_at, at=(7.72, 2.01), color=ORANGE, opacity=0)
    train_num = _dynamic_number(visual.train_acc_at, at=(7.72, 1.54), color=CYAN, width=7, decimals=2, opacity=0)
    test_num = _dynamic_number(visual.test_acc_at, at=(7.72, 1.07), color=GREEN, width=7, decimals=2, opacity=0)
    g1_num = _dynamic_number(visual.grad_norm_g1, at=(7.72, 0.60), color=PURPLE, opacity=0)
    g2_num = _dynamic_number(visual.grad_norm_g2, at=(7.72, 0.13), color=PURPLE, opacity=0)

    sample_label = Text("sample", font_size=15, color=MUTED)
    true_label = Text("true", font_size=15, color=MUTED)
    pred_label = Text("pred", font_size=15, color=MUTED, opacity=0)
    conf_label = Text("confidence %", font_size=15, color=MUTED, opacity=0)
    for obj, y in zip((sample_label, true_label, pred_label, conf_label), (-0.55, -0.92, -1.29, -1.66)):
        obj.place(anchor=TOP, at=Vec2(4.55, y))

    true_num = _dynamic_number(lambda t: visual.sample_state(t)[3], at=(7.72, -0.99), color=YELLOW, width=2, decimals=0)
    pred_num = _dynamic_number(lambda t: visual.sample_state(t)[4], at=(7.72, -1.36), color=GREEN, width=2, decimals=0, opacity=0)
    conf_num = _dynamic_number(lambda t: visual.sample_state(t)[5] * 100, at=(7.72, -1.73), color=GREEN, width=7, decimals=2, opacity=0)

    # Compact eight-point training curves.
    graph_frame = Object2D(
        Rectangle(4.55, 2.45), position=(6.35, -3.18),
        stroke=PANEL, stroke_width=0.012, z_index=8,
    )
    graph_title = Text("epoch summary", font_size=16, color=MUTED)
    graph_title.place(anchor=TOP, at=Vec2(6.35, -1.92))

    loss_max = float(np.max(trace.mean_loss))
    loss_min = float(np.min(trace.mean_loss))
    loss_span = max(1e-6, loss_max - loss_min)
    loss_points = tuple(
        Vec2(4.45 + 3.8 * i / 7, -2.55 - 0.75 * (float(v) - loss_min) / loss_span)
        for i, v in enumerate(trace.mean_loss)
    )
    train_points = tuple(
        Vec2(4.45 + 3.8 * i / 7, -3.55 - 0.72 * (1.0 - float(v)))
        for i, v in enumerate(trace.train_accuracy)
    )
    test_points = tuple(
        Vec2(4.45 + 3.8 * i / 7, -3.55 - 0.72 * (1.0 - float(v)))
        for i, v in enumerate(trace.test_accuracy)
    )
    loss_curve = DynamicGeometryObject2D(
        lambda t: _curve(loss_points, visual.completed_epochs(t)),
        style=Style.outline(ORANGE, 0.028), z_index=10,
    )
    train_curve = DynamicGeometryObject2D(
        lambda t: _curve(train_points, visual.completed_epochs(t)),
        style=Style.outline(CYAN, 0.025), z_index=10,
    )
    test_curve = DynamicGeometryObject2D(
        lambda t: _curve(test_points, visual.completed_epochs(t)),
        style=Style.outline(GREEN, 0.025), z_index=10,
    )
    loss_legend = Text("mean loss", font_size=13, color=ORANGE)
    acc_legend = Text("train / test accuracy", font_size=13, color=MUTED)
    loss_legend.place(anchor=TOP, at=Vec2(5.05, -2.22))
    acc_legend.place(anchor=TOP, at=Vec2(6.35, -3.38))

    # Dedicated formula strip: nothing else is allowed to occupy this region.
    formula_frame = Object2D(
        Rectangle(10.15, 1.45), position=(-2.55, -3.72),
        stroke=PANEL, stroke_width=0.012, z_index=8,
    )
    forward_formula = Group2D([
        Text("FORWARD", font_size=15, color=CYAN),
        Math("Z_1 = X W_1 + b_1", font_size=21, color=CYAN),
        Math('Y_1 = sigma(Z_1)   comma   Y_2 = "softmax"(Y_1 W_2 + b_2)', font_size=20, color=GREEN),
        Math("L = -log Y_(2,y)", font_size=20, color=ORANGE),
    ], opacity=0, z_index=15)
    Column(gap=0.055, at=Vec2(-2.55, -3.72)).place(*forward_formula.children)

    backward_formula = Group2D([
        Text("BACKWARD · epoch aggregate", font_size=15, color=PURPLE),
        Math('G_e = sum_(b in e) "grad"_W L_b = (W_e - W_(e+1)) / eta', font_size=21, color=PURPLE),
        Text(
            "all 938 mini-batches contribute; no per-batch gradient is animated",
            font_size=15, color=MUTED,
        ),
    ], opacity=0, z_index=15)
    Column(gap=0.075, at=Vec2(-2.55, -3.72)).place(*backward_formula.children)

    update_formula = Group2D([
        Text("UPDATE", font_size=15, color=YELLOW),
        Math("W_(e+1) = W_e - eta G_e", font_size=24, color=YELLOW),
        Math("Delta W_e = -eta G_e", font_size=20, color=WHITE),
    ], opacity=0, z_index=15)
    Column(gap=0.085, at=Vec2(-2.55, -3.72)).place(*update_formula.children)

    # During update the actual W1 map and the actual accumulated gradient map
    # move into these slots. The gradient then slides onto W1 while W1 morphs
    # to the next epoch boundary.
    weight_slot_label = Math("W_(1,e)", font_size=17, color=CYAN, opacity=0, z_index=16)
    grad_slot_label = Math("- eta G_(1,e)", font_size=17, color=PURPLE, opacity=0, z_index=16)
    plus_label = Text("+", font_size=23, color=WHITE, opacity=0, z_index=16)
    next_weight_label = Math("W_(1,e+1)", font_size=17, color=YELLOW, opacity=0, z_index=16)
    weight_slot_label.place(anchor=BOTTOM, at=Vec2(WEIGHT_SLOT_CENTER.x, 1.73))
    grad_slot_label.place(anchor=BOTTOM, at=Vec2(GRADIENT_SLOT_CENTER.x, 1.73))
    plus_label.place(anchor=BOTTOM, at=Vec2(-4.00, 2.48))
    next_weight_label.place(anchor=BOTTOM, at=Vec2(WEIGHT_SLOT_CENTER.x, 1.73))

    scene.add(
        pixels, weight_filters, gradient_filters, hidden, output, bars,
        f_input_filter, f_filter_hidden, f_w2,
        b_w2, b_hidden_filter, b_filter_input,
        title, subtitle, input_label, filters_label, hidden_label, output_label,
        *filter_numbers, *digit_labels,
        metrics_frame, metrics_title, *metric_labels,
        epoch_num, loss_num, train_num, test_num, g1_num, g2_num,
        sample_label, true_label, pred_label, conf_label, true_num, pred_num, conf_num,
        graph_frame, graph_title, loss_curve, train_curve, test_curve,
        loss_legend, acc_legend,
        formula_frame, forward_formula, backward_formula, update_formula,
        weight_slot_label, grad_slot_label, plus_label, next_weight_label,
    )

    forward_formula = scene.on(forward_formula)
    backward_formula = scene.on(backward_formula)
    update_formula = scene.on(update_formula)
    weight_filters = scene.on(weight_filters)
    gradient_filters = scene.on(gradient_filters)
    gradient_tiles = [scene.on(tile) for tile in gradient_tile_objects]
    pred_label = scene.on(pred_label)
    conf_label = scene.on(conf_label)
    pred_num = scene.on(pred_num)
    conf_num = scene.on(conf_num)
    loss_label, train_label, test_label = (
        scene.on(metric_labels[1]), scene.on(metric_labels[2]), scene.on(metric_labels[3])
    )
    g1_label, g2_label = scene.on(metric_labels[4]), scene.on(metric_labels[5])
    loss_num = scene.on(loss_num)
    train_num = scene.on(train_num)
    test_num = scene.on(test_num)
    g1_num = scene.on(g1_num)
    g2_num = scene.on(g2_num)
    weight_slot_label = scene.on(weight_slot_label)
    grad_slot_label = scene.on(grad_slot_label)
    plus_label = scene.on(plus_label)
    next_weight_label = scene.on(next_weight_label)

    # Reuse the same formula and metric panels for all eight epochs. No result
    # metric is visible before the corresponding computation has happened.
    with scene.parallel():
        result_handles = (pred_label, conf_label, pred_num, conf_num)
        summary_handles = (loss_label, train_label, test_label, loss_num, train_num, test_num)
        gradient_metric_handles = (g1_label, g2_label, g1_num, g2_num)

        for epoch in range(EPOCHS):
            start = INTRO_END + epoch * EPOCH_DURATION

            forward_formula.fade_in(duration=0.12, at=start)
            forward_formula.fade_out(duration=0.12, at=start + FORWARD_LOCAL_END - 0.12)

            # Prediction and confidence only appear once the forward wave has
            # physically reached the output layer. They disappear at reset.
            for handle in result_handles:
                handle.opacity(to=1.0, duration=0.12, at=start + 1.12)
                handle.opacity(to=0.0, duration=0.10, at=start + UPDATE_LOCAL_END)

            # Forward is complete: move the actual W1 map out of the network and
            # keep it visible as the left operand of W + (-eta G).
            weight_filters.transform(
                to=WEIGHT_SLOT_TRANSFORM, duration=0.34, at=start + FORWARD_LOCAL_END
            )
            weight_slot_label.opacity(to=1.0, duration=0.16, at=start + FORWARD_LOCAL_END + 0.12)

            backward_formula.fade_in(duration=0.12, at=start + FORWARD_LOCAL_END)
            backward_formula.fade_out(duration=0.12, at=start + BACKWARD_LOCAL_END - 0.12)
            # Reveal the eight retained gradient tiles in reverse hidden-neuron
            # order as the backward wave reaches W1.
            for order, tile in enumerate(reversed(gradient_tiles)):
                tile.opacity(
                    to=1.0, duration=0.18,
                    at=start + FORWARD_LOCAL_END + 0.50 + 0.065 * order,
                )
            for handle in gradient_metric_handles:
                handle.opacity(to=1.0, duration=0.16, at=start + FORWARD_LOCAL_END + 0.36)
                handle.opacity(to=0.0, duration=0.12, at=start + UPDATE_LOCAL_END)

            # Backward is complete. Shrink the real accumulated gradient into a
            # second slot, then slide it onto W1 to make the addition literal.
            gradient_filters.transform(
                to=GRADIENT_SLOT_TRANSFORM, duration=0.24, at=start + BACKWARD_LOCAL_END
            )
            grad_slot_label.opacity(to=1.0, duration=0.14, at=start + BACKWARD_LOCAL_END + 0.08)
            plus_label.opacity(to=1.0, duration=0.14, at=start + BACKWARD_LOCAL_END + 0.08)
            gradient_filters.transform(
                to=WEIGHT_SLOT_TRANSFORM, duration=0.28, at=start + BACKWARD_LOCAL_END + 0.24
            )
            grad_slot_label.opacity(to=0.0, duration=0.16, at=start + BACKWARD_LOCAL_END + 0.27)
            plus_label.opacity(to=0.0, duration=0.16, at=start + BACKWARD_LOCAL_END + 0.27)

            update_formula.fade_in(duration=0.12, at=start + BACKWARD_LOCAL_END)
            update_formula.fade_out(duration=0.12, at=start + UPDATE_LOCAL_END - 0.12)
            weight_slot_label.opacity(to=0.0, duration=0.14, at=start + STACK_LOCAL_END)
            next_weight_label.opacity(to=1.0, duration=0.14, at=start + STACK_LOCAL_END)
            # W_e -> W_e+1 is an ordinary retained batch transition: the two
            # complete endpoint batches are packed once and interpolated in Zig.
            weight_filters.batch(
                to=visual._static_weight_filters(epoch + 1),
                duration=UPDATE_LOCAL_END - STACK_LOCAL_END,
                at=start + STACK_LOCAL_END,
            )
            # As W_e morphs to W_e+1, the overlaid -eta G fades into it.
            gradient_filters.opacity(to=0.0, duration=0.58, at=start + STACK_LOCAL_END)

            # Epoch statistics only become visible after the update is complete.
            for handle in summary_handles:
                handle.opacity(to=1.0, duration=0.12, at=start + UPDATE_LOCAL_END - 0.06)
                if epoch < EPOCHS - 1:
                    handle.opacity(to=0.0, duration=0.10, at=start + EPOCH_DURATION - 0.12)

            # Return the newly updated W1 map to the network for the next epoch.
            weight_filters.transform(
                to=Transform2D(), duration=0.40, at=start + UPDATE_LOCAL_END
            )
            gradient_filters.transform(
                to=Transform2D(), duration=0.30, at=start + UPDATE_LOCAL_END
            )
            if epoch < EPOCHS - 1:
                # While the parent group is fully transparent, switch all eight
                # retained tiles to the next epoch in zero-duration BatchClips
                # and reset their individual reveals.
                switch_at = start + UPDATE_LOCAL_END + 0.31
                for i, tile in enumerate(gradient_tiles):
                    tile.opacity(to=0.0, duration=0.0, at=switch_at)
                    tile.batch(
                        to=visual._gradient_filter_tile(epoch + 1, i),
                        duration=0.0, at=switch_at,
                    )
                gradient_filters.opacity(to=1.0, duration=0.0, at=switch_at + 0.01)
            next_weight_label.opacity(to=0.0, duration=0.12, at=start + UPDATE_LOCAL_END + 0.12)

        # Inference uses the final trained weights and repeats the same reveal: no
        # probability/prediction is shown before the forward wave reaches output.
        forward_formula.fade_in(duration=0.15, at=TRAIN_END)
        forward_formula.fade_out(duration=0.15, at=INFERENCE_END - 0.15)
        for segment in range(4):
            start = TRAIN_END + 2.0 * segment
            for handle in result_handles:
                handle.opacity(to=1.0, duration=0.12, at=start + 1.12)
                handle.opacity(to=0.0, duration=0.10, at=start + 1.90)

    scene.wait(FINAL_END - scene.timeline.cursor)
    return scene


def random_access_probe(scene: Scene) -> None:
    times = (8.25, 23.75, 47.25, 16.5, 39.2, 8.25)
    first = scene.evaluate(times[0])
    for time in times[1:-1]:
        scene.evaluate(time)
    second = scene.evaluate(times[-1])
    if first != second:
        raise AssertionError("MNIST epoch scene is not random-access deterministic")


def benchmark_dict(
    result: TrainingResult,
    *,
    render_seconds: float | None,
    output: Path,
    fps: int,
    workers: int,
) -> dict[str, object]:
    frame_count = ceil(FINAL_END * fps)
    trace = result.trace
    return {
        "training": {
            "dataset": "MNIST 60000/10000",
            "architecture": [784, 8, 10],
            "epochs": EPOCHS,
            "batches_per_epoch": BATCHES_PER_EPOCH,
            "learning_rate": LEARNING_RATE,
            "train_seconds": result.train_seconds,
            "epoch_trace_mib": trace.memory_bytes / (1024 * 1024),
            "final_train_accuracy": result.final_train_accuracy,
            "final_test_accuracy": result.final_test_accuracy,
        },
        "visualization": {
            "w1_weights": INPUT_SIZE * HIDDEN_SIZE,
            "w1_representation": "8 complete 28x28 weight maps",
            "w2_weights": HIDDEN_SIZE * OUTPUT_SIZE,
            "gradient": "G_e=(W_e-W_{e+1})/eta, exact sum of epoch mini-batch gradients",
            "propagation": "forward lines grow left-to-right; backward gradient lines grow right-to-left",
            "duration_seconds": FINAL_END,
            "fps": fps,
            "frames": frame_count,
            "workers": workers,
            "random_access": "ok",
        },
        "render": {
            "seconds": render_seconds,
            "effective_fps": None if render_seconds is None else frame_count / render_seconds,
            "output": str(output),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Real MNIST MLP training visualized epoch by epoch")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--benchmark", type=Path, default=BENCHMARK)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--dry-run", action="store_true", help="train/build/probe without encoding video")
    args = parser.parse_args()

    for path in (TRAIN_IMG, TRAIN_LBL, TEST_IMG, TEST_LBL):
        if not path.exists():
            raise FileNotFoundError(f"missing MNIST asset: {path}")

    print("Loading MNIST...")
    X_train = load_images(TRAIN_IMG)
    y_train = load_labels(TRAIN_LBL)
    X_test = load_images(TEST_IMG)
    y_test = load_labels(TEST_LBL)

    print("Training the real 784→8→10 NumPy MLP...")
    result = train_with_epoch_trace(X_train, y_train, X_test, y_test)
    print(
        f"training={result.train_seconds:.3f}s "
        f"epoch_trace={result.trace.memory_bytes/(1024*1024):.2f} MiB "
        f"train_acc={result.final_train_accuracy:.4f} test_acc={result.final_test_accuracy:.4f}"
    )
    del X_train, y_train, X_test, y_test

    scene = build_scene(result)
    random_access_probe(scene)
    print("random-access probe: OK")

    output = args.output.resolve()
    render_seconds = None
    if not args.dry_run:
        started = perf_counter()
        scene.render_video(
            output,
            fps=args.fps,
            workers=args.workers,
            verify_random_access=True,
            preset="veryfast",
        )
        render_seconds = perf_counter() - started
        print(f"render={render_seconds:.3f}s output={output}")

    benchmark = benchmark_dict(
        result,
        render_seconds=render_seconds,
        output=output,
        fps=args.fps,
        workers=args.workers,
    )
    path = args.benchmark.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(benchmark, indent=2) + "\n")
    print(path)


if __name__ == "__main__":
    main()
