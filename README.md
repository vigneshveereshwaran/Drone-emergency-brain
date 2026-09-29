# 🚁 Autonomous Drone Emergency Brain

> **"The drone encounters the failure. Our Emergency Brain decides how to respond."**

### Explainable Autonomous Emergency Decision & Recovery System

The **Autonomous Drone Emergency Brain** is a software-first emergency decision and recovery platform designed to simulate how an autonomous drone detects failures, evaluates risks, selects a safe response, executes recovery, and independently verifies the outcome.

Instead of directly connecting failure events to predefined recovery actions, the system follows an explainable decision pipeline:

```text
MONITOR → DETECT → CLASSIFY → ASSESS IMPACT → DECIDE → RECOVER → VERIFY
```

The system is designed around deterministic decision-making, simulated airspace restrictions, energy feasibility, compound failures, explainability, and independent recovery verification.

---

## 📌 Table of Contents

* [Overview](#-overview)
* [Key Features](#-key-features)
* [System Architecture](#-system-architecture)
* [Core Design Principles](#-core-design-principles)
* [Airspace & Geofencing](#-airspace--geofencing)
* [Decision Rules](#-decision-rules)
* [Demonstration Scenarios](#-demonstration-scenarios)
* [Project Structure](#-project-structure)
* [Technology Stack](#-technology-stack)
* [Installation](#-installation)
* [Running the System](#-running-the-system)
* [REST API](#-rest-api)
* [Example Decision](#-example-decision)
* [Verification Model](#-verification-model)
* [Testing](#-testing)
* [Architecture Validation](#-architecture-validation)
* [Mission Flow](#-mission-flow)
* [Future Enhancements](#-future-enhancements)
* [Limitations](#-limitations)
* [Team](#-team)

---

# 🎯 Overview

Autonomous drones can encounter unexpected situations during missions, including:

* GPS signal loss
* Critical or low battery
* Communication failure
* Physical obstacles
* Restricted airspace
* Unauthorized movement
* Multiple simultaneous failures

A simple autopilot response such as **"Return to Home"** may not always be appropriate.

For example:

> A drone loses GPS while flying inside restricted airspace.

Simply holding position may violate the simulated airspace rules.

The **Emergency Brain** evaluates the complete situation before selecting a response.

### Example

```text
GPS = LOST
Battery = 65%
Communication = CONNECTED
Position = [50, 50]
Zone = RESTRICTED
```

The system evaluates:

```text
GPS FAILURE
      ↓
RESTRICTED AIRSPACE
      ↓
CURRENT HOVER = UNSAFE
      ↓
R5 + R7
      ↓
RELOCATE_AND_HOVER
      ↓
HZ1
```

The recovery action is then executed and independently verified using the drone's resulting telemetry.

---

# ✨ Key Features

### 🧠 Explainable Decision Engine

Every emergency decision contains:

* Selected action
* Severity
* Reason
* Evidence
* Rules fired
* Rejected alternatives
* Recovery target when applicable

### 🗺️ Simulated Airspace Intelligence

The simulator contains:

* Home/Base
* Destination
* Restricted airspace
* Private property
* Multiple recovery hover zones
* Mission route

### ⚡ Energy-Aware Decisions

The system considers:

* Current battery percentage
* Return-to-home feasibility
* Destination reachability
* Emergency landing requirements

### 🚨 Multi-Failure Detection

The Emergency Brain can reason about compound failures such as:

```text
GPS LOSS
+
COMMUNICATION LOSS
+
18% BATTERY
```

and elevate the emergency severity accordingly.

### 🔐 Security Response

Unauthorized movement or tampering triggers:

```text
SECURITY_ESCALATION
```

and generates an operator alert.

### ✅ Independent Verification

The system never assumes that a recovery action succeeded.

Instead:

```text
DECISION
   ↓
EXECUTION
   ↓
ACTUAL TELEMETRY
   ↓
VERIFICATION
   ↓
SUCCESS / PARTIAL_SUCCESS / FAILED
```

### 🧪 Headless Acceptance Testing

The project includes automated scenario execution without requiring manual interaction with the web UI.

---

# 🏗️ System Architecture

```text
                    ┌────────────────────────┐
                    │    DRONE SIMULATOR     │
                    │                        │
                    │ Position               │
                    │ Battery                │
                    │ GPS                    │
                    │ Communication          │
                    │ Obstacles              │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │       DETECTOR         │
                    │                        │
                    │ Detect failure signals │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │      CLASSIFIER        │
                    │                        │
                    │ GPS / Battery / Comm   │
                    │ Obstacle / Security    │
                    └───────────┬────────────┘
                                │
                                ▼
              ┌─────────────────────────────────────┐
              │         EMERGENCY BRAIN             │
              │                                     │
              │        Decision Engine              │
              │                                     │
              │          R1 → R14                   │
              │                                     │
              │  Risk Assessment + Explainability   │
              └──────────────────┬──────────────────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   RECOVERY EXECUTOR    │
                    │                        │
                    │ Hover                  │
                    │ Return To Home         │
                    │ Emergency Landing      │
                    │ Alternate Route        │
                    │ Relocate & Hover       │
                    └───────────┬────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │       VERIFIER         │
                    │                        │
                    │ Inspect actual state   │
                    └───────────┬────────────┘
                                │
                         ┌──────┴──────┐
                         ▼             ▼
                    SUCCESS        FAILURE
                         │             │
                         ▼             ▼
                 CONTINUE MISSION   ESCALATE
```

---

# 🧩 Core Design Principles

## 1. Decoupled Decision Engine

The Decision Engine is completely independent of the simulator and recovery actuators.

It receives standardized telemetry:

```python
decision = emergency_brain.evaluate(telemetry)
```

and produces a structured decision.

The Decision Engine must not directly control the simulated drone.

---

## 2. Failure Injection Does Not Trigger Recovery

Scenario APIs only modify simulated telemetry.

For example:

```text
POST /api/scenario/gps-loss
```

changes:

```text
gps_status = LOST
```

It does **not** directly execute:

```text
HOVER
RETURN_TO_HOME
EMERGENCY_LANDING
```

The Emergency Brain observes the changed telemetry and decides what should happen.

---

## 3. Recovery Does Not Make Decisions

The Recovery Executor only executes the decision produced by the Decision Engine.

```text
Decision Engine
      ↓
"RELOCATE_AND_HOVER"
      ↓
Recovery Executor
      ↓
Execute relocation
```

The executor does not independently decide which action is appropriate.

---

## 4. Verification Never Assumes Success

After recovery execution, the Verifier checks the actual drone state.

Possible results:

```text
SUCCESS
PARTIAL_SUCCESS
FAILED
```

For example, if the brain commands:

```text
RETURN_TO_HOME
```

the system verifies:

* Drone position
* Battery
* Navigation state
* Landing state
* Mission state

before declaring success.

---

## 5. Explainability by Design

Every decision provides a structured explanation.

Example:

```json
{
  "action": "RELOCATE_AND_HOVER",
  "reason": "GPS lost inside restricted airspace",
  "evidence": [
    "gps_status=LOST",
    "position=[50,50]",
    "zone=RESTRICTED"
  ],
  "rules_fired": [
    "R5",
    "R7"
  ],
  "rejected_options": {
    "HOVER": "Station holding is prohibited inside restricted airspace",
    "CONTINUE_MISSION": "GPS position confidence is unavailable"
  }
}
```

This makes the decision process auditable and understandable.

---

# 🗺️ Airspace & Geofencing

The simulation uses a **100 × 100 coordinate grid**.

| Area                | Type       | Coordinates                  | Behavior                             |
| ------------------- | ---------- | ---------------------------- | ------------------------------------ |
| Home                | ALLOWED    | `[10, 80]`                   | Mission origin and safe landing base |
| Destination         | ALLOWED    | `[90, 20]`                   | Planned delivery target              |
| Restricted Airspace | RESTRICTED | `x: 42–62, y: 40–60`         | No-fly zone                          |
| Private Property    | PRIVATE    | `x: 68–82, y: 30–45`         | Protected area                       |
| HZ1                 | HOVER_ZONE | Center `(36,66)`, Radius `5` | Primary recovery zone                |
| HZ2                 | HOVER_ZONE | Center `(30,45)`, Radius `5` | West recovery station                |
| HZ3                 | HOVER_ZONE | Center `(72,60)`, Radius `5` | South-East landing pad               |
| HZ4                 | HOVER_ZONE | Center `(85,12)`, Radius `5` | Perimeter recovery zone              |

### Restricted Airspace

```text
x = 42 → 62
y = 40 → 60
```

The flagship demonstration places the drone at:

```text
[50, 50]
```

which is inside the restricted zone.

---

# ⚙️ Decision Rules

The Emergency Brain currently implements **14 deterministic rules**.

| Rule | Condition                                         | Action                                 |
| ---- | ------------------------------------------------- | -------------------------------------- |
| R1   | Unauthorized movement / tampering                 | `SECURITY_ESCALATION`                  |
| R2   | Battery ≤ 20% + feasible RTH                      | `RETURN_TO_HOME`                       |
| R3   | Battery ≤ 20% + infeasible RTH                    | `EMERGENCY_LANDING`                    |
| R4   | Blocked corridor                                  | `ALTERNATE_ROUTE`                      |
| R5   | GPS lost inside restricted zone                   | `RELOCATE_AND_HOVER`                   |
| R6   | GPS lost in legal airspace                        | `HOVER`                                |
| R7   | Active restricted-airspace breach                 | `RELOCATE_AND_HOVER`                   |
| R8   | Communication loss ≤ 5 sec                        | `CONTINUE_MISSION`                     |
| R9   | Communication loss > 5 sec + navigation available | `RETURN_TO_HOME`                       |
| R10  | Communication + GPS loss                          | Safe station holding                   |
| R11  | Battery 20–30% + target reachable                 | `CONTINUE_MISSION`                     |
| R12  | Target unreachable                                | `RETURN_TO_HOME` / `EMERGENCY_LANDING` |
| R13  | GPS degraded + acceptable confidence              | `CONTINUE_MISSION`                     |
| R14  | All systems nominal                               | `CONTINUE_MISSION`                     |

---

# 🎬 Demonstration Scenarios

## Scenario 1 — GPS Loss in Restricted Airspace

**Flagship Scenario**

Initial state:

```text
Position: [50,50]
GPS: CONNECTED
Battery: Healthy
Communication: CONNECTED
Zone: RESTRICTED
```

Failure:

```text
GPS → LOST
```

Decision:

```text
GPS_FAILURE
+
RESTRICTED_ZONE
        ↓
R5 + R7
        ↓
HOVER REJECTED
        ↓
HZ1 SELECTED
        ↓
RELOCATE_AND_HOVER
```

After relocation:

```text
HZ1
 ↓
GPS RESTORED
 ↓
Verification
 ↓
Mission Resumes
 ↓
Destination
 ↓
MISSION_COMPLETED
```

---

## Scenario 2 — Critical Battery

Battery drops to:

```text
19%
```

The system evaluates RTH feasibility.

If Home is reachable:

```text
RETURN_TO_HOME
```

If Home is unreachable:

```text
EMERGENCY_LANDING
```

The landing outcome is then independently verified.

---

## Scenario 3 — Obstacle Blocked Corridor

The forward sensor detects an obstacle.

The system:

```text
OBSTACLE DETECTED
       ↓
CURRENT ROUTE REJECTED
       ↓
ALTERNATE ROUTE
       ↓
AIRSPACE VALIDATION
       ↓
DET0UR EXECUTION
       ↓
VERIFICATION
```

The alternate route must avoid restricted and protected areas.

---

## Scenario 4 — Prolonged Communication Failure

Ground communication is lost for more than five seconds.

```text
COMM LOSS > 5s
       ↓
R9
       ↓
RETURN_TO_HOME
       ↓
AUTONOMOUS RTH
       ↓
TOUCHDOWN VERIFICATION
```

---

## Scenario 5 — Multi-Failure Emergency

Simultaneous failures:

```text
GPS = LOST
COMMUNICATION = LOST
BATTERY = 18%
```

The system classifies the situation as:

```text
CRITICAL
```

and executes:

```text
EMERGENCY_LANDING
```

rather than treating each failure independently.

---

## Scenario 6 — Unauthorized Movement

During recovery or station holding, unexpected movement is detected.

```text
UNAUTHORIZED MOVEMENT
        ↓
R1
        ↓
SECURITY_ESCALATION
        ↓
OPERATOR ALERT
```

---

## Scenario 7 — Verification Failure

This scenario intentionally causes a recovery verification failure.

The system demonstrates that:

```text
COMMAND ≠ SUCCESS
```

Instead, the Verifier independently examines actual telemetry and reports:

```text
FAILED
```

when the expected recovery state was not achieved.

---

# 📁 Project Structure

A recommended project structure:

```text
autonomous-drone-emergency-brain/
│
├── app.py
├── requirements.txt
├── README.md
│
├── decision_engine/
│   ├── __init__.py
│   ├── engine.py
│   ├── rules.py
│   └── models.py
│
├── simulator/
│   ├── __init__.py
│   ├── drone.py
│   ├── mission.py
│   ├── telemetry.py
│   └── scenarios.py
│
├── recovery/
│   ├── __init__.py
│   ├── executor.py
│   └── verifier.py
│
├── geofence/
│   ├── __init__.py
│   ├── zones.py
│   └── routing.py
│
├── database/
│   └── audit.db
│
├── templates/
│   └── index.html
│
├── static/
│   ├── css/
│   ├── js/
│   └── assets/
│
└── tests/
    ├── test_decision_engine.py
    ├── test_architecture.py
    ├── test_scenarios.py
    └── headless_runner.py
```

---

# 🛠️ Technology Stack

| Technology          | Purpose                             |
| ------------------- | ----------------------------------- |
| Python              | Core application and decision logic |
| Flask               | REST API and web server             |
| HTML/CSS/JavaScript | Tactical Command Center UI          |
| SQLite              | Audit trail and event logging       |
| Pytest              | Automated testing                   |
| AST Analysis        | Architecture enforcement            |
| JSON                | Telemetry and decision exchange     |

---

# 🚀 Installation

## Requirements

* Python **3.10+**
* pip
* Git
* Modern web browser

---

## 1. Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd autonomous-drone-emergency-brain
```

---

## 2. Create a Virtual Environment

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

# ▶️ Running the Application

Start the Flask server:

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

The browser will display the **Tactical Command Center**.

---

# 🎮 Tactical Command Center

The web interface provides visibility into:

* Drone position
* Mission route
* Battery
* GPS status
* Communication status
* Current airspace
* Active failure
* Emergency severity
* Selected recovery action
* Rules fired
* Rejected actions
* Recovery status
* Verification result
* Event history

The UI is designed to make the Emergency Brain's reasoning visible during demonstrations.

---

# 📡 REST API

## System APIs

| Method | Endpoint         | Description                         |
| ------ | ---------------- | ----------------------------------- |
| `GET`  | `/`              | Tactical Command Center UI          |
| `GET`  | `/api/state`     | Current system and mission state    |
| `GET`  | `/api/telemetry` | Standardized telemetry              |
| `GET`  | `/api/decision`  | Current explainable decision        |
| `GET`  | `/api/events`    | Chronological audit events          |
| `GET`  | `/api/map`       | Airspace and recovery-zone metadata |

---

## Mission APIs

| Method | Endpoint                | Description          |
| ------ | ----------------------- | -------------------- |
| `POST` | `/api/mission/start`    | Start mission        |
| `POST` | `/api/mission/pause`    | Pause mission        |
| `POST` | `/api/mission/reset`    | Reset simulation     |
| `POST` | `/api/simulation/speed` | Set simulation speed |

Example:

```json
{
  "speed": 2
}
```

---

# 🚨 Failure Injection APIs

### GPS Loss

```http
POST /api/scenario/gps-loss
```

### GPS Restore

```http
POST /api/scenario/gps-restore
```

### Low Battery

```http
POST /api/scenario/low-battery
```

Injects:

```text
28% battery
```

### Critical Battery

```http
POST /api/scenario/critical-battery
```

Injects:

```text
18% battery
```

### Communication Loss

```http
POST /api/scenario/communication-loss
```

### Obstacle

```http
POST /api/scenario/obstacle
```

### Unauthorized Movement

```http
POST /api/scenario/unauthorized-movement
```

### Multi-Failure

```http
POST /api/scenario/multi-failure
```

Injects:

```text
GPS LOSS
+
COMMUNICATION LOSS
+
18% BATTERY
```

---

# 🎬 Automated Demo APIs

Automated closed-loop demonstrations are available through:

```http
POST /api/demo/<scenario>
```

Example:

```http
POST /api/demo/gps-loss-restricted
```

The automated scenario executes the complete pipeline:

```text
Failure Injection
      ↓
Telemetry Update
      ↓
Failure Detection
      ↓
Decision
      ↓
Recovery
      ↓
Verification
      ↓
Mission Continuation / Escalation
```

---

# 🧠 Example Explainable Decision

For GPS loss inside restricted airspace:

```json
{
  "action": "RELOCATE_AND_HOVER",
  "target": "HZ1",
  "severity": "CRITICAL",
  "reason": "GPS lost while operating inside restricted airspace",
  "evidence": [
    "GPS status is LOST",
    "Drone position is [50,50]",
    "Current zone is RESTRICTED"
  ],
  "rules_fired": [
    "R5",
    "R7"
  ],
  "rejected_options": {
    "HOVER": "Station holding is prohibited inside restricted airspace",
    "CONTINUE_MISSION": "Reliable GPS position is unavailable"
  }
}
```

This output makes the decision auditable by both humans and automated tests.

---

# 🔍 Verification Model

The system separates **command execution** from **verification**.

### Incorrect assumption

```text
Command: RETURN_TO_HOME
        ↓
Assume success
```

### Emergency Brain approach

```text
Command: RETURN_TO_HOME
        ↓
Execute
        ↓
Observe actual telemetry
        ↓
Compare expected vs actual state
        ↓
SUCCESS
PARTIAL_SUCCESS
or
FAILED
```

This allows the system to detect recovery failures instead of blindly trusting the executor.

---

# 🧪 Testing

Run the complete Pytest suite:

```bash
python -m pytest -v tests/
```

Run the headless acceptance suite:

```bash
python tests/headless_runner.py
```

The tests validate:

* Decision rules
* Scenario behavior
* Recovery outcomes
* Verification
* API behavior
* Architecture constraints

---

# 🛡️ Architecture Validation

The project includes an architecture test to ensure that the Decision Engine does not directly depend on the simulator.

Example:

```text
test_decision_engine_never_imports_simulator
```

The intended dependency direction is:

```text
Simulator
     │
     │ telemetry
     ▼
Decision Engine
     │
     │ decision
     ▼
Recovery Executor
     │
     │ resulting state
     ▼
Verifier
```

The Decision Engine must remain independent of simulator and actuator implementation details.

---

# 🔄 Mission Lifecycle

A normal mission follows:

```text
MISSION_START
      ↓
MONITOR
      ↓
TELEMETRY
      ↓
FAILURE DETECTION
      ↓
CLASSIFICATION
      ↓
RISK ASSESSMENT
      ↓
DECISION
      ↓
RECOVERY
      ↓
VERIFICATION
      ↓
┌───────────────┐
│               │
▼               ▼
SUCCESS       FAILURE
│               │
▼               ▼
CONTINUE      ESCALATE
MISSION
```

---

# 🧾 Audit Trail

Important system events are recorded in the SQLite audit trail.

Example events:

```text
MISSION_STARTED
GPS_FAILURE_DETECTED
RESTRICTED_ZONE_DETECTED
RULE_R5_FIRED
DECISION_RELOCATE_AND_HOVER
HZ1_SELECTED
RECOVERY_STARTED
GPS_RESTORED
RECOVERY_VERIFIED
MISSION_RESUMED
MISSION_COMPLETED
```

This provides a chronological record of what happened and why.

---

# 📊 Design Philosophy

The Emergency Brain follows five fundamental principles:

```text
1. DETECT — Understand what failed.

2. ASSESS — Understand the consequences.

3. DECIDE — Select the safest valid response.

4. RECOVER — Execute the selected response.

5. VERIFY — Never assume recovery succeeded.
```

The system therefore separates:

```text
WHAT HAPPENED?
        ↓
WHAT DOES IT MEAN?
        ↓
WHAT SHOULD WE DO?
        ↓
DID IT ACTUALLY WORK?
```

---

# 🔮 Future Enhancements

Potential future extensions include:

* Real drone telemetry integration
* MAVLink integration
* PX4 / ArduPilot integration
* Real-time weather data
* Dynamic no-fly-zone APIs
* Real GPS hardware integration
* Advanced energy prediction
* Machine-learning-based anomaly detection
* Reinforcement-learning recovery planning
* Multi-drone coordination
* Real-time operator control
* 3D airspace visualization
* Hardware-in-the-loop testing
* Digital twin simulation
* Formal safety verification

---

# ⚠️ Limitations

This project is a **software simulation and hackathon prototype**.

The following limitations apply:

* Airspace boundaries are simulated.
* Flight dynamics are simplified.
* Recovery zones are simulated.
* Security events represent simulated telemetry conditions.
* Battery consumption is simulated.
* GPS and communication failures are simulated.
* The system is not certified aviation software.
* Decisions should not be used as operational instructions for real aircraft.
* Real-world aviation regulations, flight-controller behavior, weather, aircraft performance, and regulatory requirements require additional integration and validation.

The architecture is intended as a foundation for future integration with real flight-controller telemetry and certified safety systems.

---

# 🏆 Hackathon MVP Goal

The MVP demonstrates that an autonomous system can move beyond:

```text
FAILURE → ALERT
```

toward:

```text
FAILURE
   ↓
UNDERSTAND
   ↓
ASSESS
   ↓
DECIDE
   ↓
EXPLAIN
   ↓
RECOVER
   ↓
VERIFY
```

The key demonstration is not simply that the drone can recover.

It is that the system can explain:

> **What failed, why the situation is dangerous, which rule was triggered, which actions were rejected, what recovery was selected, and whether the recovery actually succeeded.**

---

# 👥 Team

**Project:** Autonomous Drone Emergency Brain

**Domain:** Autonomous Systems / Drone Safety / AI Decision Systems

**Type:** Software-First Simulation & Decision Engine

---

# 📄 License

This project is intended for educational, research, and hackathon demonstration purposes.

Add an appropriate open-source license such as MIT if the repository is intended for public reuse.

---

## 🚁 MONITOR. THINK. RECOVER. VERIFY.

> **The drone encounters the failure.
> The Emergency Brain decides how to respond.**
