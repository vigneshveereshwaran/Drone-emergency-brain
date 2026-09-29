"""
Autonomous Drone Emergency Brain - Flask Application Entrypoint
Part B & V: Flask Backend, Full REST API, and Decoupled Architecture.
Flask configuration: debug=False, use_reloader=False, threaded=True.
"""

from flask import Flask, render_template, jsonify, request
import config
from database.db import init_db, get_events
from simulator.system_controller import SystemController
from simulator.scenarios import ScenarioOrchestrator


def create_app(test_config=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")

    if test_config:
        app.config.update(test_config)

    # Initialize SQLite database
    db_path = app.config.get("DB_PATH", config.DB_PATH)
    init_db(db_path)

    # Initialize central system controller
    controller = SystemController(mission_id="MISSION-001")

    # -------------------------------------------------------------
    # WEB UI ROUTE
    # -------------------------------------------------------------
    @app.route("/")
    def index():
        """Serves the main command center dashboard."""
        return render_template("index.html")

    # -------------------------------------------------------------
    # TELEMETRY & STATE QUERY ENDPOINTS
    # -------------------------------------------------------------
    @app.route("/api/state", methods=["GET"])
    def get_state():
        """Returns the current state machine and mission status."""
        return jsonify({
            "ok": True,
            "data": controller.get_state()
        })

    @app.route("/api/telemetry", methods=["GET"])
    def get_telemetry():
        """Returns the current standardized telemetry frame."""
        return jsonify({
            "ok": True,
            "data": controller.get_telemetry()
        })

    @app.route("/api/events", methods=["GET"])
    def list_events():
        """Returns chronological system events from audit trail."""
        limit = request.args.get("limit", default=50, type=int)
        events = get_events(limit=limit, db_path=db_path)
        return jsonify({
            "ok": True,
            "data": events
        })

    @app.route("/api/decision", methods=["GET"])
    def get_decision():
        """Evaluates current telemetry and returns explainable Emergency Brain decision."""
        evaluation = controller.get_decision_evaluation()
        return jsonify({
            "ok": True,
            "data": evaluation
        })

    @app.route("/api/map", methods=["GET"])
    def get_map():
        """Returns structured map geometry, waypoints, and airspace boundaries."""
        return jsonify({
            "ok": True,
            "data": controller.geofence.get_map_metadata()
        })

    # -------------------------------------------------------------
    # MISSION LIFECYCLE CONTROLS
    # -------------------------------------------------------------
    @app.route("/api/mission/start", methods=["POST"])
    def start_mission():
        """Initiates drone mission flight."""
        controller.start_mission()
        return jsonify({
            "ok": True,
            "data": {"message": "Mission started", "state": controller.get_state()}
        })

    @app.route("/api/mission/pause", methods=["POST"])
    def pause_mission():
        """Pauses active flight."""
        controller.pause_mission()
        return jsonify({
            "ok": True,
            "data": {"message": "Mission paused", "state": controller.get_state()}
        })

    @app.route("/api/mission/reset", methods=["POST"])
    def reset_mission():
        """Resets the drone, state machine, and decision latches."""
        controller.reset()
        return jsonify({
            "ok": True,
            "data": {"message": "Mission reset", "state": controller.get_state()}
        })

    @app.route("/api/simulation/speed", methods=["POST"])
    def set_simulation_speed():
        """Sets simulation speed multiplier (1x, 2x, 4x)."""
        payload = request.get_json(silent=True) or {}
        speed = payload.get("speed", 1.0)
        try:
            val = float(speed)
            if val not in (1.0, 2.0, 4.0):
                return jsonify({"ok": False, "error": "Speed must be 1, 2, or 4"}), 400
            controller.set_simulation_speed(val)
            return jsonify({"ok": True, "data": {"speed": val}})
        except ValueError:
            return jsonify({"ok": False, "error": "Invalid speed parameter"}), 400

    # -------------------------------------------------------------
    # SCENARIO FAULT INJECTION BUTTONS (Part I: Modifies ONLY simulated telemetry)
    # -------------------------------------------------------------
    @app.route("/api/scenario/gps-loss", methods=["POST"])
    def scenario_gps_loss():
        controller.inject_gps_loss()
        return jsonify({"ok": True, "data": {"message": "GPS loss injected into simulated receiver"}})

    @app.route("/api/scenario/gps-restore", methods=["POST"])
    def scenario_gps_restore():
        controller.restore_gps()
        return jsonify({"ok": True, "data": {"message": "GPS signal restored"}})

    @app.route("/api/scenario/gps-degrade", methods=["POST"])
    def scenario_gps_degrade():
        controller.inject_gps_degrade()
        return jsonify({"ok": True, "data": {"message": "GPS degraded"}})

    @app.route("/api/scenario/low-battery", methods=["POST"])
    def scenario_low_battery():
        controller.inject_battery(28.0)
        return jsonify({"ok": True, "data": {"message": "Simulated battery set to 28% (Low)"}})

    @app.route("/api/scenario/critical-battery", methods=["POST"])
    def scenario_critical_battery():
        controller.inject_battery(18.0)
        return jsonify({"ok": True, "data": {"message": "Simulated battery set to 18% (Critical)"}})

    @app.route("/api/scenario/communication-loss", methods=["POST"])
    def scenario_comm_loss():
        controller.inject_comm_loss()
        return jsonify({"ok": True, "data": {"message": "Ground link communication loss injected"}})

    @app.route("/api/scenario/communication-restore", methods=["POST"])
    def scenario_comm_restore():
        controller.restore_comm()
        return jsonify({"ok": True, "data": {"message": "Communication link restored"}})

    @app.route("/api/scenario/obstacle", methods=["POST"])
    def scenario_obstacle():
        controller.inject_obstacle()
        return jsonify({"ok": True, "data": {"message": "Obstacle injected on forward route"}})

    @app.route("/api/scenario/obstacle-clear", methods=["POST"])
    def scenario_obstacle_clear():
        controller.clear_obstacle()
        return jsonify({"ok": True, "data": {"message": "Obstacle cleared"}})

    @app.route("/api/scenario/unauthorized-movement", methods=["POST"])
    def scenario_unauthorized_movement():
        controller.inject_unauthorized_movement()
        return jsonify({"ok": True, "data": {"message": "Unauthorized movement / tampering injected"}})

    @app.route("/api/scenario/multi-failure", methods=["POST"])
    def scenario_multi_failure():
        controller.inject_multi_failure()
        return jsonify({"ok": True, "data": {"message": "Triple multi-failure emergency injected"}})

    @app.route("/api/scenario/reset", methods=["POST"])
    def scenario_reset():
        controller.restore_gps()
        controller.restore_comm()
        controller.clear_obstacle()
        controller.inject_battery(100.0)
        return jsonify({"ok": True, "data": {"message": "All faults cleared"}})

    # -------------------------------------------------------------
    # AUTOMATED DEMO SCENARIO RUNNERS (Part Y)
    # -------------------------------------------------------------
    @app.route("/api/demo/<scenario_name>", methods=["POST"])
    def run_demo_scenario(scenario_name: str):
        """Runs an automated closed-loop demonstration of any scenario."""
        orchestrator = ScenarioOrchestrator(mission_id=f"DEMO-{scenario_name.upper()}")

        scenario_map = {
            "flagship": orchestrator.run_flagship_scenario,
            "gps-loss": orchestrator.run_flagship_scenario,
            "critical-battery": orchestrator.run_critical_battery_scenario,
            "obstacle": orchestrator.run_obstacle_scenario,
            "communication": orchestrator.run_communication_failure_scenario,
            "communication-failure": orchestrator.run_communication_failure_scenario,
            "multi-failure": orchestrator.run_multi_failure_scenario,
            "unauthorized-movement": orchestrator.run_unauthorized_movement_scenario,
            "failing-verification": orchestrator.run_intentionally_failing_verification
        }

        normalized = scenario_name.lower().strip()
        runner = scenario_map.get(normalized)

        if not runner:
            return jsonify({
                "ok": False,
                "error": f"Unknown demo scenario '{scenario_name}'. Available: {list(scenario_map.keys())}"
            }), 400

        try:
            result = runner()
            return jsonify({
                "ok": True,
                "data": result
            })
        except Exception as e:
            return jsonify({
                "ok": False,
                "error": f"Demo scenario execution failed: {str(e)}"
            }), 500

    # -------------------------------------------------------------
    # STANDARDIZED ERROR HANDLERS
    # -------------------------------------------------------------
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"ok": False, "error": "Bad request"}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"ok": False, "error": "Endpoint not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"ok": False, "error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"ok": False, "error": f"Internal server error: {str(e)}"}), 500

    return app


app = create_app()

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
        use_reloader=False,
        threaded=True
    )
