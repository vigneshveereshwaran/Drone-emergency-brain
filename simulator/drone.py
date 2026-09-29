"""
VirtualDrone implementation for Autonomous Drone Simulator.
Part G: Simulated Drone with gradual kinematic movement, battery drain, GPS and communication states,
hover tracking, and fault injection interfaces.
"""

import math
from typing import List, Dict, Any, Optional
import config
from simulator.geofence import GeofenceManager
from simulator.telemetry import build_telemetry


class VirtualDrone:
    """
    Simulates drone kinematics, battery consumption, sensors, and flight modes.
    Never teleports: moves strictly by step = speed * dt along target vector.
    """

    def __init__(
        self,
        start_pos: Optional[List[float]] = None,
        destination_pos: Optional[List[float]] = None,
        geofence_mgr: Optional[GeofenceManager] = None
    ):
        self.home = list(start_pos or config.START)
        self.destination = list(destination_pos or config.DESTINATION)
        self.geofence = geofence_mgr or GeofenceManager()

        # Kinematic state
        self.position = list(self.home)
        self.last_known_position = list(self.home)
        self.altitude = 10.0          # meters
        self.speed = 0.0              # units / second
        self.max_speed = config.DRONE_SPEED
        self.flight_mode = "IDLE"     # IDLE, MISSION, HOVER, RELOCATING, RETURNING, ALTERNATE_ROUTE, LANDING, LANDED
        self.mission_status = "READY"

        # Waypoints queue
        self.target_position: Optional[List[float]] = None
        self.waypoint_queue: List[List[float]] = []

        # Energy & Battery
        self.battery = float(config.INITIAL_BATTERY)
        self.battery_consumption_rate = config.BATTERY_CONSUMPTION
        self.hover_drain_rate = config.HOVER_DRAIN

        # Sensor & Link Statuses
        self.gps_status = "CONNECTED"       # CONNECTED, DEGRADED, LOST
        self.gps_accuracy = 4.0             # meters
        self.satellites = 10
        self.communication = "CONNECTED"    # CONNECTED, LOST
        self.comm_loss_duration = 0.0       # seconds

        # Hover & Security state
        self.hover_position: Optional[List[float]] = None
        self.hover_duration = 0.0
        self.unauthorized_movement = False
        self.theft_detected = False

        # Obstacle
        self.obstacle_detected = False
        self.obstacle_position: Optional[List[float]] = None

        # Tracking
        self.actual_path: List[List[float]] = [list(self.position)]
        self.active_command_id: Optional[str] = None
        self.sim_time = 0.0

    def start_mission(self) -> None:
        """Arms drone and initiates route to destination."""
        self.flight_mode = "MISSION"
        self.mission_status = "MISSION_ACTIVE"
        self.target_position = list(self.destination)
        self.waypoint_queue.clear()
        self.speed = self.max_speed

    def pause_mission(self) -> None:
        """Pauses in-flight movement."""
        self.flight_mode = "HOVER"
        self.hover_position = list(self.position)
        self.speed = 0.0

    def reset(self) -> None:
        """Resets the drone completely to starting state."""
        self.position = list(self.home)
        self.last_known_position = list(self.home)
        self.altitude = 10.0
        self.speed = 0.0
        self.flight_mode = "IDLE"
        self.mission_status = "READY"
        self.target_position = None
        self.waypoint_queue.clear()
        self.battery = float(config.INITIAL_BATTERY)
        self.gps_status = "CONNECTED"
        self.gps_accuracy = 4.0
        self.satellites = 10
        self.communication = "CONNECTED"
        self.comm_loss_duration = 0.0
        self.hover_position = None
        self.hover_duration = 0.0
        self.unauthorized_movement = False
        self.theft_detected = False
        self.obstacle_detected = False
        self.obstacle_position = None
        self.actual_path = [list(self.position)]
        self.active_command_id = None
        self.sim_time = 0.0

    # -------------------------------------------------------------
    # KINEMATIC STEPPING & SIMULATION LOOP
    # -------------------------------------------------------------
    def step(self, dt: float) -> None:
        """
        Advances the drone by dt seconds.
        Gradual movement along target vector without teleportation.
        """
        if dt <= 0:
            return

        self.sim_time += dt

        # Update communication loss duration
        if self.communication == "LOST":
            self.comm_loss_duration += dt
        else:
            self.comm_loss_duration = 0.0

        # Handle flight modes
        if self.flight_mode in ("MISSION", "RELOCATING", "RETURNING", "ALTERNATE_ROUTE"):
            self._step_movement(dt)
        elif self.flight_mode == "HOVER":
            self._step_hover(dt)
        elif self.flight_mode == "LANDING":
            self._step_landing(dt)
        elif self.flight_mode in ("IDLE", "LANDED"):
            self.speed = 0.0

        # Update GPS last known position:
        # When GPS is connected: last_known_position tracks current_position
        # When GPS is lost: last_known_position remains frozen!
        if self.gps_status != "LOST":
            self.last_known_position = list(self.position)

    def _step_movement(self, dt: float) -> None:
        """Gradual movement towards target_position."""
        if not self.target_position:
            # Check if there is a next waypoint in queue
            if self.waypoint_queue:
                self.target_position = self.waypoint_queue.pop(0)
            else:
                self.speed = 0.0
                return

        dx = self.target_position[0] - self.position[0]
        dy = self.target_position[1] - self.position[1]
        dist_to_target = math.hypot(dx, dy)

        if dist_to_target < 0.001:
            # Arrived at waypoint
            self.position = list(self.target_position)
            if self.waypoint_queue:
                self.target_position = self.waypoint_queue.pop(0)
            else:
                self.target_position = None
                self.speed = 0.0
                if self.flight_mode == "MISSION":
                    self.flight_mode = "IDLE"
                    self.mission_status = "MISSION_COMPLETED"
                elif self.flight_mode == "RETURNING":
                    self.flight_mode = "LANDED"
                    self.altitude = 0.0
                elif self.flight_mode == "RELOCATING":
                    # Reached recovery zone -> transition to HOVER
                    self.flight_mode = "HOVER"
                    self.hover_position = list(self.position)
                    self.hover_duration = 0.0
            return

        # Gradual step: never exceed speed * dt
        max_dist = self.max_speed * dt
        step_dist = min(dist_to_target, max_dist)
        ratio = step_dist / dist_to_target

        move_x = dx * ratio
        move_y = dy * ratio

        self.position[0] += move_x
        self.position[1] += move_y
        self.speed = step_dist / dt

        # Battery consumption for movement
        drain = step_dist * self.battery_consumption_rate
        self.battery = max(0.0, self.battery - drain)

        # Path history record
        if not self.actual_path or math.hypot(self.position[0] - self.actual_path[-1][0], self.position[1] - self.actual_path[-1][1]) > 0.5:
            self.actual_path.append(list(self.position))

    def _step_hover(self, dt: float) -> None:
        """Tracking hover station and duration."""
        self.speed = 0.0
        self.hover_duration += dt

        # Hover battery drain
        hover_drain = dt * self.hover_drain_rate
        self.battery = max(0.0, self.battery - hover_drain)

        # Ensure hover anchor exists
        if not self.hover_position:
            self.hover_position = list(self.position)

        # Check drift tolerance
        drift = math.hypot(self.position[0] - self.hover_position[0], self.position[1] - self.hover_position[1])
        if drift > config.HOVER_RADIUS and not self.active_command_id:
            self.unauthorized_movement = True

    def _step_landing(self, dt: float) -> None:
        """Descends safely to ground."""
        self.speed = 0.0
        descend_rate = 2.0  # meters / second
        self.altitude = max(0.0, self.altitude - descend_rate * dt)
        if self.altitude <= 0.0:
            self.altitude = 0.0
            self.flight_mode = "LANDED"

    # -------------------------------------------------------------
    # FAULT INJECTION (Part I: Modifies ONLY simulated environment)
    # -------------------------------------------------------------
    def inject_gps_loss(self) -> None:
        """Simulates complete loss of GPS lock."""
        self.gps_status = "LOST"
        self.gps_accuracy = 99.0
        self.satellites = 0

    def restore_gps(self) -> None:
        """Restores healthy GPS lock."""
        self.gps_status = "CONNECTED"
        self.gps_accuracy = 4.0
        self.satellites = 10
        self.last_known_position = list(self.position)

    def inject_gps_degrade(self, accuracy: float = 25.0, satellites: int = 4) -> None:
        """Simulates degraded GPS accuracy and satellite count."""
        self.gps_status = "DEGRADED"
        self.gps_accuracy = accuracy
        self.satellites = satellites

    def inject_battery(self, level: float) -> None:
        """Sets simulated battery level (e.g. 28% for LOW, 18% for CRITICAL)."""
        self.battery = max(0.0, min(100.0, level))

    def inject_communication_loss(self) -> None:
        """Simulates loss of communication uplink/heartbeat."""
        self.communication = "LOST"
        self.comm_loss_duration = 0.0

    def restore_communication(self) -> None:
        """Restores communication link."""
        self.communication = "CONNECTED"
        self.comm_loss_duration = 0.0

    def inject_obstacle(self, pos: Optional[List[float]] = None) -> None:
        """Injects simulated obstacle along route."""
        self.obstacle_detected = True
        self.obstacle_position = list(pos or [50.0, 50.0])

    def clear_obstacle(self) -> None:
        """Clears simulated obstacle."""
        self.obstacle_detected = False
        self.obstacle_position = None

    def inject_unauthorized_movement(self, dx: float = 8.0, dy: float = 8.0) -> None:
        """
        Simulates physical displacement (wind gust / external tampering) without an authorized command.
        Distinguishable from commanded movement.
        """
        self.position[0] += dx
        self.position[1] += dy
        self.unauthorized_movement = True
        self.theft_detected = True
        self.actual_path.append(list(self.position))

    def inject_multi_failure(self) -> None:
        """Simulates simultaneous GPS loss, communication failure, and critical battery (18%)."""
        self.inject_gps_loss()
        self.inject_communication_loss()
        self.inject_battery(18.0)

    # -------------------------------------------------------------
    # RECOVERY EXECUTION (Called ONLY by recovery module)
    # -------------------------------------------------------------
    def command_hover(self, command_id: str) -> None:
        """Commands drone to hold station at current position."""
        self.flight_mode = "HOVER"
        self.hover_position = list(self.position)
        self.hover_duration = 0.0
        self.speed = 0.0
        self.active_command_id = command_id
        self.unauthorized_movement = False

    def command_relocate(self, target_pos: List[float], command_id: str) -> None:
        """Commands drone to fly to a safe recovery zone."""
        self.flight_mode = "RELOCATING"
        self.target_position = list(target_pos)
        self.waypoint_queue.clear()
        self.speed = self.max_speed
        self.active_command_id = command_id
        self.unauthorized_movement = False

    def command_return_to_home(self, command_id: str) -> None:
        """Commands drone to return to home coordinate."""
        self.flight_mode = "RETURNING"
        self.target_position = list(self.home)
        self.waypoint_queue.clear()
        self.speed = self.max_speed
        self.active_command_id = command_id
        self.unauthorized_movement = False

    def command_alternate_route(self, waypoints: List[List[float]], command_id: str) -> None:
        """Commands drone to navigate around obstacle via alternate waypoints."""
        if not waypoints:
            return
        self.flight_mode = "ALTERNATE_ROUTE"
        self.target_position = list(waypoints[0])
        self.waypoint_queue = [list(wp) for wp in waypoints[1:]]
        self.speed = self.max_speed
        self.active_command_id = command_id
        self.unauthorized_movement = False

    def command_emergency_landing(self, command_id: str) -> None:
        """Commands immediate controlled vertical descent."""
        self.flight_mode = "LANDING"
        self.target_position = None
        self.waypoint_queue.clear()
        self.speed = 0.0
        self.active_command_id = command_id
        self.unauthorized_movement = False

    def command_resume_mission(self) -> None:
        """Resumes navigation to destination once recovery is verified."""
        self.flight_mode = "MISSION"
        self.target_position = list(self.destination)
        self.waypoint_queue.clear()
        self.speed = self.max_speed
        self.active_command_id = None
        self.unauthorized_movement = False

    # -------------------------------------------------------------
    # TELEMETRY EXPORT
    # -------------------------------------------------------------
    def get_telemetry(self) -> Dict[str, Any]:
        """Generates real-time telemetry frame conforming to Part F."""
        zone_type = self.geofence.get_zone_type(self.position)
        return build_telemetry(
            position=self.position,
            last_known_position=self.last_known_position,
            battery=self.battery,
            gps_status=self.gps_status,
            gps_accuracy=self.gps_accuracy,
            satellites=self.satellites,
            communication=self.communication,
            comm_loss_duration=self.comm_loss_duration,
            obstacle_detected=self.obstacle_detected,
            flight_mode=self.flight_mode,
            mission_status=self.mission_status,
            speed=self.speed,
            altitude=self.altitude,
            zone_type=zone_type,
            hover_position=self.hover_position,
            hover_duration=self.hover_duration,
            unauthorized_movement=self.unauthorized_movement,
            theft_detected=self.theft_detected,
            active_command_id=self.active_command_id,
            timestamp=self.sim_time,
            home=self.home,
            destination=self.destination,
            consumption_rate=self.battery_consumption_rate
        )
