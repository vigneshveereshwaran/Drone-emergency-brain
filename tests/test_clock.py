"""
Tests for simulator/clock.py
Validates FakeClock determinism and RealClock time scaling.
"""

import time
import pytest
from simulator.clock import FakeClock, RealClock


def test_fake_clock_advance():
    clock = FakeClock(10.0)
    assert clock.now() == 10.0

    clock.advance(5.5)
    assert clock.now() == 15.5

    with pytest.raises(ValueError):
        clock.advance(-1.0)


def test_real_clock_scaling():
    clock = RealClock(time_scale=1.0)
    t0 = clock.now()
    time.sleep(0.05)
    t1 = clock.now()
    assert (t1 - t0) >= 0.04

    clock.time_scale = 2.0
    assert clock.time_scale == 2.0
