"""
Tests for simulator/engine_loop.py
Validates SimulationEngine stepping and thread-safe telemetry sampling.
"""

import pytest
import config
from simulator.engine_loop import SimulationEngine
from simulator.clock import FakeClock


def test_simulation_engine_step():
    clock = FakeClock(0.0)
    engine = SimulationEngine(clock=clock, tick_rate=10.0)
    engine.drone.start_mission()

    # Step engine 10 times (1 second total)
    for _ in range(10):
        telem = engine.step()

    assert telem["timestamp"] == pytest.approx(1.0, rel=1e-3)
    assert telem["flight_mode"] == "MISSION"
    assert telem["speed"] > 0.0
    assert telem["battery"] < 100.0


def test_simulation_engine_reset():
    clock = FakeClock(0.0)
    engine = SimulationEngine(clock=clock)
    engine.drone.start_mission()
    engine.step(5.0)

    assert engine.drone.position != config.START
    engine.reset()
    assert engine.drone.position == config.START
    assert engine.drone.battery == 100.0
