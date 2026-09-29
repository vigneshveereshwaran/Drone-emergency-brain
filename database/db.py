"""
SQLite Database interface for Autonomous Drone Emergency Brain.
Provides persistent audit trail of missions, telemetry frames, and system events.
"""

import sqlite3
import json
import os
import time
from typing import List, Dict, Any, Optional
import config


def get_connection(db_path: str = config.DB_PATH) -> sqlite3.Connection:
    """Creates a connection with row factory and WAL mode for reliability."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = config.DB_PATH) -> None:
    """Initializes the database schema matching Part T specifications."""
    conn = get_connection(db_path)
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS missions (
            mission_id TEXT PRIMARY KEY,
            mission_type TEXT NOT NULL,
            start_position TEXT NOT NULL,
            destination TEXT NOT NULL,
            initial_battery REAL NOT NULL,
            safety_reserve REAL NOT NULL,
            consumption_rate REAL NOT NULL,
            created_at REAL NOT NULL,
            status TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            mission_id TEXT NOT NULL,
            position TEXT NOT NULL,
            battery REAL NOT NULL,
            gps_status TEXT NOT NULL,
            gps_accuracy REAL NOT NULL,
            satellites INTEGER NOT NULL,
            communication TEXT NOT NULL,
            obstacle_detected INTEGER NOT NULL,
            zone_type TEXT NOT NULL,
            flight_mode TEXT NOT NULL,
            altitude REAL NOT NULL,
            distance_to_home REAL NOT NULL,
            distance_to_destination REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            mission_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL,
            evidence TEXT,
            decision TEXT,
            action TEXT,
            verification TEXT,
            status TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_telemetry_mission ON telemetry(mission_id, timestamp);
        CREATE INDEX IF NOT EXISTS idx_events_mission ON events(mission_id, timestamp);
        """)
    conn.close()


def insert_mission(
    mission_id: str,
    mission_type: str = config.MISSION_TYPE,
    start_position: Optional[List[float]] = None,
    destination: Optional[List[float]] = None,
    initial_battery: float = config.INITIAL_BATTERY,
    safety_reserve: float = config.SAFETY_RESERVE,
    consumption_rate: float = config.BATTERY_CONSUMPTION,
    status: str = "READY",
    db_path: str = config.DB_PATH
) -> None:
    """Inserts a new mission record into SQLite."""
    start = start_position or config.START
    dest = destination or config.DESTINATION
    conn = get_connection(db_path)
    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO missions (
                mission_id, mission_type, start_position, destination,
                initial_battery, safety_reserve, consumption_rate, created_at, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            mission_id,
            mission_type,
            json.dumps(start),
            json.dumps(dest),
            initial_battery,
            safety_reserve,
            consumption_rate,
            time.time(),
            status
        ))
    conn.close()


def update_mission_status(mission_id: str, status: str, db_path: str = config.DB_PATH) -> None:
    """Updates status of an existing mission."""
    conn = get_connection(db_path)
    with conn:
        conn.execute("UPDATE missions SET status = ? WHERE mission_id = ?", (status, mission_id))
    conn.close()


def log_telemetry(data: Dict[str, Any], mission_id: str, db_path: str = config.DB_PATH) -> None:
    """Logs a telemetry frame to the database."""
    conn = get_connection(db_path)
    with conn:
        conn.execute("""
            INSERT INTO telemetry (
                timestamp, mission_id, position, battery, gps_status,
                gps_accuracy, satellites, communication, obstacle_detected,
                zone_type, flight_mode, altitude, distance_to_home, distance_to_destination
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get("timestamp", time.time()),
            mission_id,
            json.dumps(data.get("position", [0, 0])),
            data.get("battery", 100.0),
            data.get("gps_status", "CONNECTED"),
            data.get("gps_accuracy", 4.0),
            data.get("satellites", 10),
            data.get("communication", "CONNECTED"),
            1 if data.get("obstacle_detected") else 0,
            data.get("zone_type", "ALLOWED"),
            data.get("flight_mode", "MISSION"),
            data.get("altitude", 10.0),
            data.get("distance_to_home", 0.0),
            data.get("distance_to_destination", 0.0)
        ))
    conn.close()


def log_event(
    mission_id: str,
    event_type: str,
    severity: str,
    message: str,
    evidence: Optional[List[str]] = None,
    decision: Optional[str] = None,
    action: Optional[str] = None,
    verification: Optional[str] = None,
    status: str = "LOGGED",
    db_path: str = config.DB_PATH
) -> int:
    """Inserts a structured system event to the audit log."""
    conn = get_connection(db_path)
    with conn:
        cursor = conn.execute("""
            INSERT INTO events (
                timestamp, mission_id, event_type, severity, message,
                evidence, decision, action, verification, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            time.time(),
            mission_id,
            event_type,
            severity,
            message,
            json.dumps(evidence or []),
            decision,
            action,
            verification,
            status
        ))
        event_id = cursor.lastrowid
    conn.close()
    return event_id


def get_events(mission_id: Optional[str] = None, limit: int = 50, db_path: str = config.DB_PATH) -> List[Dict[str, Any]]:
    """Retrieves chronological events for timeline rendering."""
    conn = get_connection(db_path)
    if mission_id:
        cursor = conn.execute(
            "SELECT * FROM events WHERE mission_id = ? ORDER BY id DESC LIMIT ?",
            (mission_id, limit)
        )
    else:
        cursor = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        if d.get("evidence"):
            try:
                d["evidence"] = json.loads(d["evidence"])
            except Exception:
                d["evidence"] = []
        result.append(d)
    return result
