"""
Simulation Engine Loop.
Orchestrates virtual drone kinematics, clock ticks, and thread-safe telemetry sampling.
"""

import time
import threading
from typing import Dict, Any, Optional
from simulator.drone import VirtualDrone
from simulator.clock import Clock, RealClock, FakeClock
from simulator.geofence import GeofenceManager


class SimulationEngine:
    """
    Thread-safe simulation orchestrator.
    Executes physics steps at configurable tick frequency and time scale.
    """

    def __init__(
        self,
        drone: Optional[VirtualDrone] = None,
        clock: Optional[Clock] = None,
        tick_rate: float = 10.0  # 10 Hz (0.1s dt per tick)
    ):
        self.geofence = GeofenceManager()
        self.drone = drone or VirtualDrone(geofence_mgr=self.geofence)
        self.clock = clock or RealClock()
        self.tick_rate = tick_rate
        self.dt = 1.0 / tick_rate

        self._lock = threading.Lock()
        self._is_running = False
        self._thread: Optional[threading.Thread] = None

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._is_running

    def step(self, dt: Optional[float] = None) -> Dict[str, Any]:
        """Performs a single deterministic simulation step."""
        step_dt = dt if dt is not None else self.dt
        with self._lock:
            self.clock.advance(step_dt)
            self.drone.step(step_dt)
            return self.drone.get_telemetry()

    def get_telemetry(self) -> Dict[str, Any]:
        """Thread-safe retrieval of latest telemetry frame."""
        with self._lock:
            return self.drone.get_telemetry()

    def set_time_scale(self, scale: float) -> None:
        """Sets real-time simulation scale (1x, 2x, 4x)."""
        with self._lock:
            if isinstance(self.clock, RealClock):
                self.clock.time_scale = scale

    def start_loop(self) -> None:
        """Starts real-time simulation background loop."""
        with self._lock:
            if self._is_running:
                return
            self._is_running = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop_loop(self) -> None:
        """Stops the real-time simulation loop."""
        with self._lock:
            self._is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _run_loop(self) -> None:
        """Background loop executing at tick_rate."""
        last_time = time.time()
        while True:
            with self._lock:
                if not self._is_running:
                    break
            now = time.time()
            elapsed = now - last_time
            if elapsed >= self.dt:
                self.step(self.dt)
                last_time = now
            else:
                time.sleep(max(0.001, self.dt - elapsed))

    def reset(self) -> None:
        """Resets engine and drone."""
        with self._lock:
            self.drone.reset()
            if isinstance(self.clock, FakeClock):
                self.clock.reset(0.0)
