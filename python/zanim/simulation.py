from __future__ import annotations

from copy import deepcopy
from math import floor, isfinite
from threading import RLock
from typing import Callable, Generic, TypeVar

StateT = TypeVar("StateT")


class Simulation(Generic[StateT]):
    """Deterministic global state advanced with a fixed simulation step.

    ``Simulation`` is independent from Scene objects. Renderables bind to the
    shared state through ``Scene.bind(..., simulation, ...)`` and only read it.
    The simulation itself owns fixed-step integration and random-access
    checkpoints so seeking does not depend on the order frames are requested.

    ``step`` may either mutate and return ``None`` or return the next state.
    ``clone`` defaults to ``copy.deepcopy`` and can be replaced for large custom
    states (for example NumPy arrays) when a cheaper exact copy is available.
    """

    def __init__(
        self,
        initial_state: StateT,
        step: Callable[[StateT, float], StateT | None],
        *,
        hz: float = 120.0,
        checkpoint_interval: float = 1.0,
        clone: Callable[[StateT], StateT] = deepcopy,
    ) -> None:
        hz = float(hz)
        checkpoint_interval = float(checkpoint_interval)
        if not isfinite(hz) or hz <= 0.0:
            raise ValueError("Simulation hz must be finite and positive")
        if not isfinite(checkpoint_interval) or checkpoint_interval <= 0.0:
            raise ValueError("checkpoint_interval must be finite and positive")
        if not callable(step):
            raise TypeError("Simulation step must be callable")
        if not callable(clone):
            raise TypeError("Simulation clone must be callable")

        self.hz = hz
        self.dt = 1.0 / hz
        self.checkpoint_interval = checkpoint_interval
        self._checkpoint_stride = max(1, int(round(checkpoint_interval * hz)))
        self._step = step
        self._clone = clone
        self._initial = clone(initial_state)
        self._checkpoints: dict[int, StateT] = {0: clone(self._initial)}
        self._cursor_step = 0
        self._cursor_state = clone(self._initial)
        self._last_time: float | None = None
        self._last_state: StateT | None = None
        self._lock = RLock()

    @property
    def checkpoint_count(self) -> int:
        return len(self._checkpoints)

    def clear_cache(self) -> None:
        """Discard generated checkpoints while preserving the initial state."""
        with self._lock:
            self._checkpoints = {0: self._clone(self._initial)}
            self._cursor_step = 0
            self._cursor_state = self._clone(self._initial)
            self._last_time = None
            self._last_state = None

    def _advance(self, state: StateT, dt: float) -> StateT:
        result = self._step(state, float(dt))
        return state if result is None else result

    def _state_at_shared(self, time: float) -> StateT:
        """Internal read-only sample shared by all bindings in one frame.

        The returned state must not be mutated by binding providers. It is a
        working copy, never a stored checkpoint, so accidental provider writes
        cannot corrupt checkpoint history, but they could affect another binding
        evaluated at the same time.
        """
        time = float(time)
        if not isfinite(time) or time < 0.0:
            raise ValueError("Simulation time must be finite and >= 0")

        with self._lock:
            if self._last_time is not None and abs(time - self._last_time) <= 1e-15:
                assert self._last_state is not None
                return self._last_state

            whole_steps = int(floor(time * self.hz + 1e-12))
            base_time = whole_steps / self.hz
            if base_time > time + 1e-12:
                whole_steps -= 1
                base_time = whole_steps / self.hz
            remainder = max(0.0, time - base_time)

            if whole_steps >= self._cursor_step:
                step_index = self._cursor_step
                state = self._clone(self._cursor_state)
            else:
                step_index = max(step for step in self._checkpoints if step <= whole_steps)
                state = self._clone(self._checkpoints[step_index])

            while step_index < whole_steps:
                state = self._advance(state, self.dt)
                step_index += 1
                if step_index % self._checkpoint_stride == 0:
                    self._checkpoints.setdefault(step_index, self._clone(state))

            # Keep one exact fixed-grid cursor for efficient forward playback.
            # The returned sample remains a separate working copy so a fractional
            # remainder never changes the canonical cursor state.
            self._cursor_step = whole_steps
            self._cursor_state = self._clone(state)
            if remainder > 1e-12:
                state = self._advance(state, remainder)

            self._last_time = time
            self._last_state = state
            return state

    def state_at(self, time: float) -> StateT:
        """Return an independent state snapshot at absolute simulation time."""
        return self._clone(self._state_at_shared(time))
