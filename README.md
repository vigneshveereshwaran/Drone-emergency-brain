# 🚁 AUTONOMOUS DRONE EMERGENCY BRAIN

> **"The drone encounters the failure. Our Emergency Brain decides how to respond."**
>
> *Final Hackathon MVP — Explainable Autonomous Emergency Decision & Recovery System*

---

## 📌 Executive Summary
Standard drone autopilots simply alert on failure or perform rudimentary return-to-home without considering dynamic legal constraints, energy viability, or compound sensor degradation. 

The **Autonomous Drone Emergency Brain** is a software-first virtual drone emergency decision and recovery system. It bridges the gap between raw telemetry monitoring and closed-loop recovery execution by implementing an explainable, deterministic response pipeline:

```text
MONITOR → DETECT → CLASSIFY → ASSESS IMPACT → DECIDE → RECOVER → VERIFY
```

---

## 🏗️ Architectural Core Principles

1. **Decoupled Decision Engine (Fifth Absolute Rule)**:
   - The Decision Engine is 100% decoupled from the simulator and actuators. It receives standardized telemetry and outputs structured decisions and commands.
   - Enforced by automated AST unit tests (`test_decision_engine_never_imports_simulator`).
2. **Failure Buttons Never Directly Call Recovery (First Absolute Rule)**:
   - Fault injection buttons (`/api/scenario/*`) modify **only** simulated sensor conditions (e.g. `gps_status = 'LOST'`).
   - They **never** directly invoke recovery commands (`hover`, `return_to_home`, etc.).
3. **Recovery Does Not Make Decisions (Second Absolute Rule)**:
   - The Decision Engine determines the response. The Recovery Executor simply executes it.
4. **Verification Must Never Assume Success (Third Absolute Rule)**:
   - Every recovery action is independently inspected by observing the drone's actual resulting state (`SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`).
5. **Explainability by Design (Fourth Absolute Rule)**:
   - Every decision outputs: `reason`, `evidence`, `rules_fired`, and `rejected_options` with detailed rationale explaining why alternative actions (such as holding station inside restricted airspace) were rejected.

---

## 🗺️ Airspace & Geofencing Grid (100 × 100)

| Area | Type | Coordinates | Behavior / Rule |
| :--- | :--- | :--- | :--- |
| **Start / Home** | ALLOWED | `[10.0, 80.0]` | Mission origin & primary safe landing base |
| **Destination** | ALLOWED | `[90.0, 20.0]` | Planned delivery target |
| **Restricted Airspace** | RESTRICTED | `x: 42–62, y: 40–60` | No-Fly Zone. Route crosses at `[50, 50]`. Station holding strictly forbidden! |
| **Private Property** | PRIVATE | `x: 68–82, y: 30–45` | Protected ground property |
| **Hover Zone 1 (HZ1)** | HOVER_ZONE | Center `(36, 66)`, Radius 5 | Primary South-West recovery zone for flagship scenario |
| **Hover Zone 2 (HZ2)** | HOVER_ZONE | Center `(30, 45)`, Radius 5 | West outpost recovery station |
| **Hover Zone 3 (HZ3)** | HOVER_ZONE | Center `(72, 60)`, Radius 5 | South-East landing pad |
| **Hover Zone 4 (HZ4)** | HOVER_ZONE | Center `(85, 12)`, Radius 5 | North-East perimeter zone |

---

## ⚡ Decision Rules Matrix (R1 – R14)

- **R1 (SECURITY)**: Unauthorized movement / tampering $\rightarrow$ `SECURITY_ESCALATION`
- **R2 (CRITICAL BATTERY - RTH)**: Battery $\le 20\%$ with feasible RTH $\rightarrow$ `RETURN_TO_HOME`
- **R3 (CRITICAL BATTERY - LAND)**: Battery $\le 20\%$ with infeasible RTH $\rightarrow$ `EMERGENCY_LANDING`
- **R4 (OBSTACLE)**: Blocked corridor $\rightarrow$ `ALTERNATE_ROUTE` (verified legally clear detour)
- **R5 (FLAGSHIP: GPS LOST IN RESTRICTED ZONE)**: GPS Lost at `[50, 50]` $\rightarrow$ Rejects current hover $\rightarrow$ `RELOCATE_AND_HOVER` to HZ1
- **R6 (GPS LOST IN LEGAL AIRSPACE)**: GPS Lost in safe airspace $\rightarrow$ `HOVER`
- **R7 (RESTRICTED AIRSPACE INCURSION)**: Active breach $\rightarrow$ `RELOCATE_AND_HOVER`
- **R8 (SHORT COMM LOSS)**: Loss $\le 5$s $\rightarrow$ `CONTINUE_MISSION` (Autonomous transit)
- **R9 (PROLONGED COMM LOSS)**: Loss $> 5$s with navigation $\rightarrow$ `RETURN_TO_HOME` failsafe
- **R10 (COMM + GPS LOSS)**: Compound loss $\rightarrow$ Safe station holding
- **R11 (LOW BATTERY - CONTINUE)**: $20\% < \text{batt} \le 30\%$ with reachable target $\rightarrow$ `CONTINUE_MISSION`
- **R12 (LOW BATTERY - RTH/LAND)**: Target unreachable $\rightarrow$ `RETURN_TO_HOME` / `EMERGENCY_LANDING`
- **R13 (GPS DEGRADED)**: Mild degradation with acceptable confidence $\rightarrow$ `CONTINUE_MISSION`
- **R14 (NOMINAL)**: All systems healthy $\rightarrow$ `CONTINUE_MISSION`

---

## 🎬 Demonstrated Scenarios

1. **Scenario 1 (Flagship) — GPS Loss over Restricted Zone**:
   - Drone cruises along planned route into restricted zone at `[50, 50]`.
   - GPS signal is lost.
   - Detector flags `GPS_FAILURE` + `RESTRICTED_ZONE`.
   - Emergency Brain rejects hovering at `[50, 50]` due to aviation regulations.
   - Brain selects `HZ1` as nearest valid recovery zone.
   - Drone relocates to `HZ1` and establishes safe hover.
   - GPS is restored and verified $\rightarrow$ Mission resumes to destination $\rightarrow$ `MISSION_COMPLETED`.
2. **Scenario 2 — Critical Battery Return-To-Home**:
   - Drone battery drops to 19% $\rightarrow$ Energy feasibility confirms RTH is reachable $\rightarrow$ Safe landing at Home base.
3. **Scenario 3 — Obstacle Blocked Corridor**:
   - Forward sensor detects physical obstruction $\rightarrow$ Safe multi-leg detour generated clear of restricted/private airspace $\rightarrow$ Avoidance verified.
4. **Scenario 4 — Prolonged Communication Failure**:
   - Ground link drops for $> 5$s $\rightarrow$ Failsafe autonomous RTH initiated $\rightarrow$ Touchdown verified.
5. **Scenario 5 — Multi-Failure Emergency**:
   - Simultaneous GPS Loss + Comm Loss + 18% Battery $\rightarrow$ Compound severity elevated to `CRITICAL` $\rightarrow$ Immediate emergency landing.
6. **Scenario 6 — Unauthorized Movement Lockout**:
   - External tampering/displacement during station holding $\rightarrow$ Immediate security escalation and operator alert.
7. **Scenario 7 — Intentionally Failing Verification**:
   - Demonstrates that the Verifier independently audits telemetry without assuming success.

---

## 🚀 Quickstart & Installation

### Requirements
- Python 3.10+
- Flask & pytest

### Setup
```bash
pip install -r requirements.txt
```

### Running the Tactical Command Center Web UI
```bash
python app.py
```
Open your browser to: **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

### Running the Headless Acceptance Suite
```bash
python tests/headless_runner.py
```

### Running the Pytest Test Suite
```bash
python -m pytest -v tests/
```

---

## 📡 REST API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Serves Dark Tactical Command Center UI |
| `GET` | `/api/state` | System state machine and mission status |
| `GET` | `/api/telemetry` | Standardized Part F telemetry frame |
| `GET` | `/api/decision` | Current Emergency Brain explainable decision & risk |
| `GET` | `/api/events` | Chronological SQLite audit trail events |
| `GET` | `/api/map` | Airspace boundaries and hover zones metadata |
| `POST` | `/api/mission/start` | Initiates drone flight |
| `POST` | `/api/mission/pause` | Pauses drone flight |
| `POST` | `/api/mission/reset` | Resets simulation and state machine |
| `POST` | `/api/simulation/speed` | Sets speed scaling (`{"speed": 1}` or `2` or `4`) |
| `POST` | `/api/scenario/gps-loss` | Simulates GPS loss (telemetry only) |
| `POST` | `/api/scenario/gps-restore` | Restores GPS signal lock |
| `POST` | `/api/scenario/low-battery` | Injects 28% low battery |
| `POST` | `/api/scenario/critical-battery` | Injects 18% critical battery |
| `POST` | `/api/scenario/communication-loss` | Injects ground link loss |
| `POST` | `/api/scenario/obstacle` | Injects corridor obstacle |
| `POST` | `/api/scenario/unauthorized-movement` | Injects unauthorized movement / tampering |
| `POST` | `/api/scenario/multi-failure` | Injects triple failure (No GPS, No Comm, 18% Batt) |
| `POST` | `/api/demo/<scenario>` | Executes automated closed-loop scenario |

---

## ⚖️ Honest Limitations Disclaimer (Part Z)
- Geofence airspace boundaries and flight dynamics are simulated for demonstration purposes.
- Security escalation represents simulated unauthorized movement detection and telemetry response.
- The Emergency Brain architecture is software-first and designed for flight controller telemetry integration, not certified aviation hardware.
#   D r o n e - e m e r g e n c y - b r a i n  
 