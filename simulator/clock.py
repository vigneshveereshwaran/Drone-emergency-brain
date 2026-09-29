"""
Simulation Clock for Autonomous Drone Simulator.
Supports RealClock (with time multipliers: 1x, 2x, 4x) and FakeClock (deterministic stepping for headless tests).
"""

import time
from abc import ABC, abstractmethod


class Clock(ABC):
    @abstractmethod
    def now(self) -> float:
        """Returns the current simulated time in seconds."""
        pass

    @abstractmethod
    def advance(self, dt: float) -> None:
        """Advances clock by dt seconds (used by FakeClock)."""
        pass


class RealClock(Clock):
    """Real-time clock scaled by a simulation multiplier (1x, 2x, 4x)."""

    def __init__(self, time_scale: float = 1.0):
        self._time_scale = time_scale
        self._start_real_time = time.time()
        self._accumulated_sim_time = 0.0
        self._last_real_time = self._start_real_time

    @property
    def time_scale(self) -> float:
        return self._time_scale

    @time_scale.setter
    def time_scale(self, scale: float) -> None:
        # Commit elapsed time at old scale before switching
        current_real = time.time()
        self._accumulated_sim_time += (current_real - self._last_real_time) * self._time_scale
        self._last_real_time = current_real
        self._time_scale = max(0.1, min(10.0, scale))

    def now(self) -> float:
        current_real = time.time()
        elapsed_real = current_real - self._last_real_time
        return self._accumulated_sim_time + (elapsed_real * self._time_scale)

    def advance(self, dt: float) -> None:
        """For RealClock, advance manually offsets accumulated time."""
        self._accumulated_sim_time += dt


class FakeClock(Clock):
    """Deterministic simulated clock for headless unit and integration tests."""

    def __init__(self, initial_time: float = 0.0):
        self._sim_time = initial_time

    def now(self) -> float:
        return self._sim_time

    def advance(self, dt: float) -> None:
        if dt < 0:
            raise ValueError("Time cannot advance backwards")
        self._sim_time += dt

    def reset(self, initial_time: float = 0.0) -> None:
        self._sim_time = initial_time
