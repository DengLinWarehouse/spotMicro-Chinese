(function () {
  const sessionId = "session-" + Math.random().toString(36).slice(2, 10);
  const stateEls = {
    runtimeState: document.getElementById("runtime-state"),
    selectedMode: document.getElementById("selected-mode"),
    armedState: document.getElementById("armed-state"),
    estopState: document.getElementById("estop-state"),
    faultState: document.getElementById("fault-state"),
    controlSource: document.getElementById("control-source"),
    selectedMapName: document.getElementById("selected-map-name"),
    speedLevelLabel: document.getElementById("speed-level-label"),
    speedLevelDisplay: document.getElementById("speed-level-display"),
    lastUpdateLabel: document.getElementById("last-update-label"),
    lastActionLabel: document.getElementById("last-action-label"),
    requestFeedback: document.getElementById("request-feedback"),
    backendPill: document.getElementById("backend-pill"),
    rosPill: document.getElementById("ros-pill"),
    mapPreviewMeta: document.getElementById("map-preview-meta"),
    mapsList: document.getElementById("maps-list"),
    forwardAxisLabel: document.getElementById("forward-axis-label"),
    turnAxisLabel: document.getElementById("turn-axis-label"),
    mapPreviewImage: document.getElementById("map-preview-image"),
  };

  const joystick = {
    base: document.getElementById("joystick-base"),
    stick: document.getElementById("joystick-stick"),
    active: false,
    pointerId: null,
    forward: 0,
    turn: 0,
  };

  let currentStatus = null;
  let lastPreviewStamp = 0;

  function setFeedback(message) {
    stateEls.requestFeedback.textContent = message;
  }

  function humanNow() {
    return new Date().toLocaleTimeString("zh-CN", { hour12: false });
  }

  async function requestJson(url, options) {
    const response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    const payload = await response.json();
    return { response, payload };
  }

  async function loadStatus() {
    try {
      const { payload } = await requestJson("/api/status");
      if (payload.ok) {
        renderStatus(payload.status);
      }
    } catch (error) {
      setFeedback("Status load failed: " + error.message);
    }
  }

  async function pingSession() {
    try {
      await requestJson("/api/session/ping", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId }),
      });
    } catch (error) {
      setFeedback("Session ping failed: " + error.message);
    }
  }

  async function loadMaps() {
    try {
      const { payload } = await requestJson("/api/maps");
      if (!payload.ok) return;
      const maps = Array.isArray(payload.maps) ? payload.maps : [];
      stateEls.mapsList.innerHTML = "";
      if (!maps.length) {
        const li = document.createElement("li");
        li.textContent = "No maps registered";
        stateEls.mapsList.appendChild(li);
        return;
      }
      maps.forEach((map) => {
        const li = document.createElement("li");
        li.textContent = map.display_name + " (" + map.map_id + ")";
        stateEls.mapsList.appendChild(li);
      });
    } catch (error) {
      setFeedback("Map list load failed: " + error.message);
    }
  }

  function renderStatus(status) {
    currentStatus = status;
    stateEls.runtimeState.textContent = status.runtime_state;
    stateEls.selectedMode.textContent = status.selected_mode;
    stateEls.armedState.textContent = status.armed ? "Yes" : "No";
    stateEls.estopState.textContent = status.estop_latched ? "Latched" : "Clear";
    stateEls.faultState.textContent = status.fault_active ? status.fault_reason || "Active" : "None";
    stateEls.controlSource.textContent = status.current_control_source;
    stateEls.selectedMapName.textContent =
      (status.selected_map && status.selected_map.display_name) || "No map selected";
    stateEls.speedLevelLabel.textContent = String(status.speed_level);
    stateEls.speedLevelDisplay.textContent = String(status.speed_level);
    stateEls.lastUpdateLabel.textContent = humanNow();
    stateEls.lastActionLabel.textContent =
      status.last_action && status.last_action.action
        ? status.last_action.action + " · " + (status.last_action.code || "")
        : "No action yet";

    stateEls.backendPill.textContent = "Backend online";
    stateEls.backendPill.className = "pill pill-ok";
    stateEls.rosPill.textContent = status.ros_connected ? "ROS connected" : "ROS disconnected";
    stateEls.rosPill.className = "pill " + (status.ros_connected ? "pill-ok" : "pill-danger");

    document.querySelectorAll(".mode-button").forEach((button) => {
      button.classList.toggle("active", button.dataset.mode === status.selected_mode);
    });

    const previewMode = ["MANUAL_MAPPING", "AUTO_EXPLORE_MAPPING", "AUTO_PATROL"].includes(status.selected_mode);
    stateEls.mapPreviewMeta.textContent = previewMode
      ? "Preview refreshed " + humanNow()
      : "Preview kept visible here for plumbing checks";

    if (status.last_action) {
      setFeedback(
        [
          "Action: " + status.last_action.action,
          "Accepted: " + String(status.last_action.accepted),
          "Code: " + status.last_action.code,
          "Message: " + status.last_action.message,
        ].join("\n")
      );
    }
  }

  async function postMode(mode) {
    try {
      const { payload } = await requestJson("/api/mode/select", {
        method: "POST",
        body: JSON.stringify({ mode }),
      });
      if (payload.status) renderStatus(payload.status);
      setFeedback(JSON.stringify(payload, null, 2));
    } catch (error) {
      setFeedback("Mode request failed: " + error.message);
    }
  }

  async function postAction(action) {
    try {
      const { payload } = await requestJson("/api/action", {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      if (payload.status) renderStatus(payload.status);
      setFeedback(JSON.stringify(payload, null, 2));
    } catch (error) {
      setFeedback("Action request failed: " + error.message);
    }
  }

  async function setSpeedLevel(nextLevel) {
    try {
      const { payload } = await requestJson("/api/speed-level", {
        method: "POST",
        body: JSON.stringify({ speed_level: nextLevel }),
      });
      if (payload.status) renderStatus(payload.status);
      setFeedback(JSON.stringify(payload, null, 2));
    } catch (error) {
      setFeedback("Speed update failed: " + error.message);
    }
  }

  async function sendManualIntent() {
    if (!joystick.active && Math.abs(joystick.forward) < 0.001 && Math.abs(joystick.turn) < 0.001) {
      return;
    }
    try {
      const { payload } = await requestJson("/api/manual-intent", {
        method: "POST",
        body: JSON.stringify({
          session_id: sessionId,
          forward_axis: joystick.forward,
          turn_axis: joystick.turn,
        }),
      });
      if (payload.status) renderStatus(payload.status);
    } catch (error) {
      setFeedback("Manual intent failed: " + error.message);
    }
  }

  function refreshPreview() {
    lastPreviewStamp += 1;
    stateEls.mapPreviewImage.src = "/api/map-preview?t=" + lastPreviewStamp;
  }

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function updateJoystickVisual(clientX, clientY) {
    const rect = joystick.base.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const dx = clientX - cx;
    const dy = clientY - cy;
    const radius = rect.width * 0.34;
    const distance = Math.hypot(dx, dy);
    const scale = distance > radius ? radius / distance : 1;
    const limitedX = dx * scale;
    const limitedY = dy * scale;

    joystick.turn = clamp(limitedX / radius, -1, 1);
    joystick.forward = clamp(-limitedY / radius, -1, 1);

    joystick.stick.style.transform = `translate(calc(-50% + ${limitedX}px), calc(-50% + ${limitedY}px))`;
    stateEls.forwardAxisLabel.textContent = joystick.forward.toFixed(2);
    stateEls.turnAxisLabel.textContent = joystick.turn.toFixed(2);
  }

  function resetJoystick(send = true) {
    joystick.active = false;
    joystick.pointerId = null;
    joystick.forward = 0;
    joystick.turn = 0;
    joystick.stick.style.transform = "translate(-50%, -50%)";
    stateEls.forwardAxisLabel.textContent = "0.00";
    stateEls.turnAxisLabel.textContent = "0.00";
    if (send) {
      sendManualIntent();
    }
  }

  joystick.base.addEventListener("pointerdown", (event) => {
    joystick.active = true;
    joystick.pointerId = event.pointerId;
    joystick.base.setPointerCapture(event.pointerId);
    updateJoystickVisual(event.clientX, event.clientY);
    sendManualIntent();
  });

  joystick.base.addEventListener("pointermove", (event) => {
    if (!joystick.active || joystick.pointerId !== event.pointerId) return;
    updateJoystickVisual(event.clientX, event.clientY);
  });

  joystick.base.addEventListener("pointerup", (event) => {
    if (joystick.pointerId !== event.pointerId) return;
    resetJoystick(true);
  });

  joystick.base.addEventListener("pointercancel", () => resetJoystick(true));

  document.getElementById("refresh-status").addEventListener("click", async () => {
    await loadStatus();
    await loadMaps();
    refreshPreview();
  });

  document.querySelectorAll(".mode-button").forEach((button) => {
    button.addEventListener("click", () => postMode(button.dataset.mode));
  });

  document.getElementById("start-button").addEventListener("click", () => postAction("START"));
  document.getElementById("safe-stop-button").addEventListener("click", () => postAction("SAFE_STOP"));
  document.getElementById("estop-button").addEventListener("click", () => postAction("ESTOP"));

  document.getElementById("speed-down").addEventListener("click", () => {
    const current = currentStatus ? Number(currentStatus.speed_level || 0) : 0;
    setSpeedLevel(current - 1);
  });

  document.getElementById("speed-up").addEventListener("click", () => {
    const current = currentStatus ? Number(currentStatus.speed_level || 0) : 0;
    setSpeedLevel(current + 1);
  });

  setInterval(loadStatus, 800);
  setInterval(pingSession, 1000);
  setInterval(loadMaps, 2500);
  setInterval(refreshPreview, 2500);
  setInterval(() => {
    if (joystick.active) sendManualIntent();
  }, 120);

  loadStatus();
  loadMaps();
  pingSession();
  refreshPreview();
})();
