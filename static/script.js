/**
 * Autonomous Drone Emergency Brain - Command Center Frontend Logic
 * Implements real-time telemetry polling, SVG flight map animation,
 * dynamic Emergency Brain explainability updates, and scenario triggers.
 */

let pollInterval = null;
let currentSpeed = 1;
let lastEventCount = 0;

document.addEventListener("DOMContentLoaded", () => {
    console.log("Tactical Command Center Interface initialized.");
    startPolling();
});

function startPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollDashboard();
    pollInterval = setInterval(pollDashboard, 250); // 4 Hz refresh
}

async function pollDashboard() {
    try {
        const [stateRes, telemRes, decRes, eventsRes] = await Promise.all([
            fetch("/api/state").then(r => r.json()),
            fetch("/api/telemetry").then(r => r.json()),
            fetch("/api/decision").then(r => r.json()),
            fetch("/api/events?limit=25").then(r => r.json())
        ]);

        if (stateRes.ok) updateStateUI(stateRes.data);
        if (telemRes.ok) updateTelemetryUI(telemRes.data);
        if (decRes.ok) updateBrainUI(decRes.data);
        if (eventsRes.ok) updateEventsUI(eventsRes.data);

    } catch (err) {
        console.warn("Polling tick error (backend updating):", err);
    }
}

// -------------------------------------------------------------
// UI UPDATERS
// -------------------------------------------------------------

function updateStateUI(state) {
    const stateEl = document.getElementById("meta-state");
    if (stateEl) {
        stateEl.textContent = state.state;
        stateEl.className = "meta-val badge-state";
        if (state.state.includes("FAIL") || state.state.includes("ABORT")) {
            stateEl.classList.add("crit");
        } else if (state.state.includes("RECOVER") || state.state.includes("DECISION")) {
            stateEl.classList.add("warn");
        }
    }

    const timeEl = document.getElementById("meta-time");
    if (timeEl && state.sim_time !== undefined) {
        timeEl.textContent = `${state.sim_time.toFixed(1)}s`;
    }

    const missionEl = document.getElementById("meta-mission-id");
    if (missionEl && state.mission_id) {
        missionEl.textContent = state.mission_id;
    }

    // Update pipeline track
    updatePipelineTrack(state.state);

    // Update recovery card status
    const recBadge = document.getElementById("recovery-state-badge");
    if (recBadge) {
        recBadge.textContent = state.state;
    }
}

function updatePipelineTrack(currentState) {
    const steps = {
        "pipe-monitor": ["READY", "MISSION_ACTIVE", "MISSION_RESUMED"],
        "pipe-detect": ["FAILURE_DETECTED"],
        "pipe-classify": ["ASSESSING"],
        "pipe-decide": ["DECISION_SELECTED"],
        "pipe-recover": ["RECOVERY_EXECUTING"],
        "pipe-verify": ["VERIFYING", "MISSION_COMPLETED"]
    };

    let activeKey = "pipe-monitor";
    for (const [key, states] of Object.entries(steps)) {
        if (states.includes(currentState)) {
            activeKey = key;
            break;
        }
    }

    const keys = ["pipe-monitor", "pipe-detect", "pipe-classify", "pipe-decide", "pipe-recover", "pipe-verify"];
    let reached = true;
    for (const k of keys) {
        const el = document.getElementById(k);
        if (!el) continue;
        if (k === activeKey) {
            el.className = "pipeline-step active";
            reached = false;
        } else if (reached) {
            el.className = "pipeline-step completed";
        } else {
            el.className = "pipeline-step";
        }
    }
}

function updateTelemetryUI(telem) {
    // 1. Coordinates readouts
    const pos = telem.position || [10.0, 80.0];
    const lastGps = telem.last_known_position || pos;
    document.getElementById("map-drone-pos").textContent = `[${pos[0].toFixed(1)}, ${pos[1].toFixed(1)}]`;
    document.getElementById("map-last-gps").textContent = `[${lastGps[0].toFixed(1)}, ${lastGps[1].toFixed(1)}]`;

    // 2. SVG Map Drone Vehicle Position
    const droneG = document.getElementById("drone-vehicle");
    if (droneG) {
        droneG.setAttribute("transform", `translate(${pos[0]}, ${pos[1]})`);
    }

    // 3. Update Path Trail
    const trailEl = document.getElementById("drone-path-trail");
    if (trailEl) {
        const existing = trailEl.getAttribute("points") || "";
        const newPt = `${pos[0].toFixed(1)},${pos[1].toFixed(1)}`;
        if (!existing.endsWith(newPt)) {
            trailEl.setAttribute("points", existing + " " + newPt);
        }
    }

    // 4. Obstacle marker visibility
    const obsMarker = document.getElementById("map-obstacle-marker");
    if (obsMarker) {
        obsMarker.style.display = telem.obstacle_detected ? "block" : "none";
    }

    // 5. Battery Bar
    const batt = telem.battery !== undefined ? telem.battery : 100.0;
    const battBar = document.getElementById("telem-battery-bar");
    const battPct = document.getElementById("telem-battery-pct");
    if (battBar && battPct) {
        battPct.textContent = `${batt.toFixed(1)}%`;
        battBar.style.width = `${Math.max(0, Math.min(100, batt))}%`;
        battBar.className = "battery-fill";
        if (batt <= 20.0) {
            battBar.classList.add("crit");
            battPct.style.color = "var(--accent-rose)";
        } else if (batt <= 30.0) {
            battBar.classList.add("low");
            battPct.style.color = "var(--accent-amber)";
        } else {
            battPct.style.color = "var(--accent-emerald)";
        }
    }

    // 6. Metrics Grid
    setText("telem-gps-status", telem.gps_status);
    setClass("telem-gps-status", telem.gps_status === "CONNECTED" ? "m-val status-green" : (telem.gps_status === "DEGRADED" ? "m-val status-amber" : "m-val status-red"));

    setText("telem-gps-acc", `${(telem.gps_accuracy || 0).toFixed(1)} m`);
    setText("telem-sats", telem.satellites || 0);
    setText("telem-gps-conf", (telem.gps_confidence !== undefined ? telem.gps_confidence : 1.0).toFixed(2));
    setText("telem-speed", `${(telem.speed || 0).toFixed(1)} u/s`);
    setText("telem-altitude", `${(telem.altitude || 0).toFixed(1)} m`);
    setText("telem-dist-home", `${(telem.distance_to_home || 0).toFixed(1)} u`);
    setText("telem-dist-dest", `${(telem.distance_to_destination || 0).toFixed(1)} u`);

    const zoneEl = document.getElementById("telem-zone-type");
    if (zoneEl) {
        zoneEl.textContent = telem.zone_type || "ALLOWED";
        zoneEl.className = "m-val " + (
            telem.zone_type === "RESTRICTED" ? "zone-restricted" :
            telem.zone_type === "PRIVATE" ? "zone-private" :
            telem.zone_type === "HOVER_ZONE" ? "zone-hover" : "zone-allowed"
        );
    }

    // 7. Subsystem Fault Matrix
    setSubsysState("card-gps", "subsys-gps-state", telem.gps_status === "CONNECTED", telem.gps_status);
    setSubsysState("card-battery", "subsys-battery-state", batt > 20.0, batt <= 20.0 ? "CRITICAL" : (batt <= 30.0 ? "LOW" : "NOMINAL"));
    setSubsysState("card-comm", "subsys-comm-state", telem.communication === "CONNECTED", telem.communication);
    setSubsysState("card-obstacle", "subsys-obstacle-state", !telem.obstacle_detected, telem.obstacle_detected ? "BLOCKED" : "CLEAR");
    setSubsysState("card-geofence", "subsys-geofence-state", telem.zone_type !== "RESTRICTED" && telem.zone_type !== "PRIVATE", telem.zone_type === "RESTRICTED" ? "INTRUSION" : (telem.zone_type === "PRIVATE" ? "PRIVATE" : "COMPLIANT"));
    setSubsysState("card-security", "subsys-security-state", !telem.unauthorized_movement, telem.unauthorized_movement ? "BREACH" : "LOCKED");

    // 8. Flight Mode in Recovery panel
    setText("rec-flight-mode", telem.flight_mode || "MISSION");
}

function setSubsysState(cardId, textId, isOk, label) {
    const card = document.getElementById(cardId);
    const text = document.getElementById(textId);
    if (!card || !text) return;

    if (isOk) {
        card.className = "subsys-card ok";
        text.textContent = label || "OK";
    } else {
        card.className = "subsys-card fault";
        text.textContent = label || "FAULT";
    }
}

function updateBrainUI(evaluation) {
    const decision = evaluation.decision || {};
    const risk = evaluation.risk || {};

    // 1. Decision Badge
    const decBadge = document.getElementById("brain-decision-badge");
    if (decBadge) {
        decBadge.textContent = decision.decision || "CONTINUE_MISSION";
        decBadge.className = "badge-decision";
        if (decision.severity === "CRITICAL") decBadge.classList.add("crit");
        else if (decision.severity === "HIGH") decBadge.classList.add("warn");
    }

    // 2. Reason Text
    setText("brain-reason", decision.reason || "Operating under normal autonomous flight path parameters.");

    // 3. Observed Evidence
    const evidenceList = document.getElementById("brain-evidence-list");
    if (evidenceList) {
        evidenceList.innerHTML = "";
        const items = decision.evidence && decision.evidence.length > 0 ? decision.evidence : ["Nominal flight conditions verified."];
        items.forEach(ev => {
            const li = document.createElement("li");
            li.textContent = ev;
            evidenceList.appendChild(li);
        });
    }

    // 4. Rule Fired
    const rulesFired = decision.rules_fired && decision.rules_fired.length > 0 ? decision.rules_fired.join(", ") : "R14_NOMINAL";
    setText("brain-rule-id", rulesFired);

    // 5. Target Station
    const target = decision.target_position || [90.0, 20.0];
    setText("brain-target-pos", `[${target[0].toFixed(1)}, ${target[1].toFixed(1)}]`);

    // Target Crosshair on Map
    const crosshair = document.getElementById("map-target-crosshair");
    if (crosshair) {
        if (decision.decision !== "CONTINUE_MISSION" && decision.target_position) {
            crosshair.style.display = "block";
            crosshair.setAttribute("transform", `translate(${target[0]}, ${target[1]})`);
            setText("target-crosshair-text", decision.selected_zone_id || "TARGET");
        } else {
            crosshair.style.display = "none";
        }
    }

    // 6. Rejected Options
    const rejectedContainer = document.getElementById("brain-rejected-list");
    if (rejectedContainer) {
        rejectedContainer.innerHTML = "";
        const rejected = decision.rejected_options || [];
        if (rejected.length === 0) {
            const item = document.createElement("div");
            item.className = "rejected-item";
            item.innerHTML = `<span class="rejected-name">Nominal Transit</span><span class="rejected-reason">Clear corridor parameters; no emergency alternative required.</span>`;
            rejectedContainer.appendChild(item);
        } else {
            rejected.forEach(r => {
                const item = document.createElement("div");
                item.className = "rejected-item";
                item.innerHTML = `<span class="rejected-name">${r.option || r.zone_id}</span><span class="rejected-reason">${r.reason}</span>`;
                rejectedContainer.appendChild(item);
            });
        }
    }

    // 7. Recovery card details
    setText("rec-action-type", decision.decision || "CONTINUE_MISSION");
    setText("rec-target-pos", `[${target[0].toFixed(1)}, ${target[1].toFixed(1)}]`);

    // 8. Risk Assessment Score and Breakdown
    const scoreNum = document.getElementById("risk-score-num");
    const scoreCircle = document.querySelector(".score-circle");
    const riskBandBadge = document.getElementById("risk-band-badge");
    const riskName = document.getElementById("risk-level-name");
    const riskSummary = document.getElementById("risk-summary-text");

    const totalPts = risk.total_score || 0;
    const band = risk.overall_risk || "LOW";

    if (scoreNum) scoreNum.textContent = totalPts;
    if (riskBandBadge) {
        riskBandBadge.textContent = band;
        riskBandBadge.className = "badge-risk-band " + band.toLowerCase();
    }
    if (riskName) {
        riskName.textContent = `${band} RISK LEVEL (${totalPts} PTS)`;
    }
    if (scoreCircle) {
        scoreCircle.className = "score-circle";
        if (band === "CRITICAL") scoreCircle.classList.add("crit");
        else if (band === "HIGH" || band === "MEDIUM") scoreCircle.classList.add("warn");
    }

    // Render risk factors
    const factorsContainer = document.getElementById("risk-factors-container");
    if (factorsContainer) {
        factorsContainer.innerHTML = "";
        const factors = risk.factors || [];
        if (factors.length === 0) {
            factorsContainer.innerHTML = `<div class="risk-factor-item"><span class="rf-name">Nominal Corridors</span><span class="rf-pts">+0</span></div>`;
        } else {
            factors.forEach(f => {
                const row = document.createElement("div");
                row.className = "risk-factor-item";
                row.innerHTML = `<span class="rf-name">${f.factor}</span><span class="rf-pts">+${f.points}</span>`;
                factorsContainer.appendChild(row);
            });
        }
    }
}

function updateEventsUI(events) {
    const timeline = document.getElementById("events-timeline");
    if (!timeline || !events) return;

    if (events.length === lastEventCount) return;
    lastEventCount = events.length;

    timeline.innerHTML = "";
    events.forEach(ev => {
        const row = document.createElement("div");
        const sevClass = (ev.severity === "CRITICAL" || ev.severity === "HIGH") ? "crit" : (ev.severity === "MEDIUM" ? "warn" : "ok");
        row.className = `timeline-event-row ${sevClass}`;

        const ts = typeof ev.timestamp === "number" ? ev.timestamp.toFixed(1) : ev.timestamp;
        row.innerHTML = `
            <div class="te-header">
                <span class="te-type">${ev.event_type}</span>
                <span class="te-time">${ts}s</span>
            </div>
            <div class="te-msg">${ev.message}</div>
        `;
        timeline.appendChild(row);
    });
}

// -------------------------------------------------------------
// USER ACTIONS & CONTROLS
// -------------------------------------------------------------

async function startMission() {
    await fetch("/api/mission/start", { method: "POST" });
    pollDashboard();
}

async function pauseMission() {
    await fetch("/api/mission/pause", { method: "POST" });
    pollDashboard();
}

async function resetMission() {
    await fetch("/api/mission/reset", { method: "POST" });
    const trailEl = document.getElementById("drone-path-trail");
    if (trailEl) trailEl.setAttribute("points", "10,80");
    lastEventCount = 0;
    pollDashboard();
}

async function setSpeed(s) {
    currentSpeed = s;
    document.querySelectorAll(".btn-speed").forEach(btn => btn.classList.remove("active"));
    const activeBtn = document.getElementById(`btn-speed-${s}`);
    if (activeBtn) activeBtn.classList.add("active");

    await fetch("/api/simulation/speed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ speed: s })
    });
}

async function injectFault(action) {
    console.log(`Injecting simulated fault: ${action}`);
    await fetch(`/api/scenario/${action}`, { method: "POST" });
    pollDashboard();
}

async function runDemo(scenarioName) {
    console.log(`Executing automated demo scenario: ${scenarioName}`);
    await fetch(`/api/demo/${scenarioName}`, { method: "POST" });
    pollDashboard();
}

// Helper utilities
function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function setClass(id, className) {
    const el = document.getElementById(id);
    if (el) el.className = className;
}
