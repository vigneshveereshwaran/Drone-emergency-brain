"""
Tests for simulator/drone.py
Phase 1 Exit Gate validations:
- Drone moves gradually (no teleportation)
- Battery decreases proportionally to distance and hover
- Last known GPS position freezes during GPS loss
- Unauthorized movement is distinguishable from commanded movement
"""

import math
import pytest
import config
from simulator.drone import VirtualDrone
from simulator.geofence import GeofenceManager


@pytest.fixture
def drone():
    return VirtualDrone()


def test_drone_initial_state(drone):
    """Drone initializes at home with full battery and healthy sensors."""
    assert drone.position == config.START
    assert drone.last_known_position == config.START
    assert drone.battery == 100.0
    assert drone.gps_status == "CONNECTED"
    assert drone.communication == "CONNECTED"
    assert drone.flight_mode == "IDLE"
    assert drone.unauthorized_movement is False


def test_gradual_movement_no_teleportation(drone):
    """
    Exit Gate: Drone moves gradually along target vector; distance per step <= speed * dt.
    Never teleports to destination.
    """
    drone.start_mission()
    dt = 0.5  # half second step
    max_step_distance = drone.max_speed * dt  # 5.0 * 0.5 = 2.5 units

    initial_pos = list(drone.position)
    drone.step(dt)
    pos_after_step = list(drone.position)

    dist_moved = math.hypot(pos_after_step[0] - initial_pos[0], pos_after_step[1] - initial_pos[1])
    assert dist_moved > 0.0
    assert dist_moved <= max_step_distance + 1e-4
    assert dist_moved == pytest.approx(max_step_distance, rel=1e-3)
    # Drone must not have teleported anywhere near destination (90, 20)
    assert math.hypot(pos_after_step[0] - config.DESTINATION[0], pos_after_step[1] - config.DESTINATION[1]) > 50.0


def test_battery_decreases_with_movement(drone):
    """Exit Gate: Battery decreases continuously as distance is traversed."""
    drone.start_mission()
    initial_battery = drone.battery

    # Move for 10 seconds (10 steps of 1.0s)
    for _ in range(10):
        drone.step(1.0)

    assert drone.battery < initial_battery
    # Total distance moved = speed * 10 = 5 * 10 = 50 units
    # Expected consumption = 50 * 0.4 = 20%
    expected_battery = initial_battery - (50.0 * config.BATTERY_CONSUMPTION)
    assert drone.battery == pytest.approx(expected_battery, rel=1e-2)


def test_battery_decreases_during_hover(drone):
    """Battery decreases during hover based on HOVER_DRAIN rate."""
    drone.flight_mode = "HOVER"
    drone.hover_position = list(drone.position)
    initial_battery = drone.battery

    drone.step(20.0)  # 20 seconds hover
    expected_drain = 20.0 * config.HOVER_DRAIN
    assert drone.battery == pytest.approx(initial_battery - expected_drain, rel=1e-2)
    assert drone.hover_duration == pytest.approx(20.0, rel=1e-2)


def test_last_known_gps_position_freezes_during_gps_loss(drone):
    """
    Exit Gate: When GPS status is 'LOST', last_known_position freezes at failure location
    even as the drone continues to move.
    """
    drone.start_mission()

    # Move for 4 seconds
    for _ in range(4):
        drone.step(1.0)

    # Position before failure
    pos_at_failure = list(drone.position)
    assert drone.last_known_position == pytest.approx(pos_at_failure, rel=1e-3)

    # Simulate GPS loss
    drone.inject_gps_loss()
    assert drone.gps_status == "LOST"

    # Move for another 6 seconds without GPS
    for _ in range(6):
        drone.step(1.0)

    # Physical position has progressed
    current_pos = list(drone.position)
    assert math.hypot(current_pos[0] - pos_at_failure[0], current_pos[1] - pos_at_failure[1]) > 10.0

    # last_known_position must remain frozen at failure point!
    assert drone.last_known_position == pytest.approx(pos_at_failure, rel=1e-3)
    assert drone.last_known_position != current_pos

    # Restoring GPS unfreezes last_known_position
    drone.restore_gps()
    assert drone.last_known_position == pytest.approx(current_pos, rel=1e-3)


def test_unauthorized_movement_distinguishable_from_commanded(drone):
    """
    Exit Gate: Unauthorized movement (tampering/drift) is clearly flagged,
    whereas authorized commanded movement is NOT flagged as unauthorized.
    """
    # 1. Normal commanded flight does not flag unauthorized movement
    drone.start_mission()
    drone.step(2.0)
    assert drone.unauthorized_movement is False

    # 2. Hover station holding without external disturbance
    drone.command_hover("CMD-001")
    drone.step(2.0)
    assert drone.unauthorized_movement is False

    # 3. External disturbance / tampering injection
    drone.inject_unauthorized_movement(dx=10.0, dy=5.0)
    assert drone.unauthorized_movement is True
    assert drone.theft_detected is True

    # 4. Telemetry correctly reflects unauthorized movement
    telem = drone.get_telemetry()
    assert telem["unauthorized_movement"] is True
    assert telem["theft_detected"] is True

    # 5. An authorized recovery command clears the flag
    drone.command_return_to_home("CMD-002")
    assert drone.unauthorized_movement is False
