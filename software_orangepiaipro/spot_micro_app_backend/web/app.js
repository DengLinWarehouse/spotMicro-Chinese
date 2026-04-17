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
    currentMapCard: document.getElementById("current-map-card"),
    currentMapTitle: document.getElementById("current-map-title"),
    currentMapDetail: document.getElementById("current-map-detail"),
    currentMapBadge: document.getElementById("current-map-badge"),
    mapPreviewImage: document.getElementById("map-preview-image"),
    saveMapButton: document.getElementById("save-map-button"),
    renameMapButton: document.getElementById("rename-map-button"),
    confirmMapSelectButton: document.getElementById("confirm-map-select-button"),
    pendingMapName: document.getElementById("pending-map-name"),
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
  let currentMaps = [];
  let currentPreview = null;
  let pendingMapId = "";
  let pendingMapName = "";
  let lastPreviewStamp = 0;
  let initialMapStateKnown = false;
  let startupRestoreHint = false;

  function setFeedback(message) {
    stateEls.requestFeedback.textContent = message;
  }

  function humanNow() {
    return new Date().toLocaleTimeString("zh-CN", { hour12: false });
  }

  function humanTime(timestampSec) {
    if (!timestampSec) return "-";
    const value = Number(timestampSec);
    if (!Number.isFinite(value) || value <= 0) return "-";
    return new Date(value * 1000).toLocaleString("zh-CN", { hour12: false });
  }

  function isMappingMode(mode) {
    return mode === "MANUAL_MAPPING" || mode === "AUTO_EXPLORE_MAPPING";
  }

  function supportsMapPreview(mode) {
    return mode === "MANUAL_MAPPING" || mode === "AUTO_EXPLORE_MAPPING" || mode === "AUTO_PATROL";
  }

  function getSelectedMap(status) {
    return status && status.selected_map ? status.selected_map : null;
  }

  function renderCurrentMapCard(status) {
    const selected = getSelectedMap(status);
    if (!selected || !selected.map_id) {
      stateEls.currentMapCard.className = "current-map-card current-map-card-empty";
      stateEls.currentMapTitle.textContent = "未选择地图";
      stateEls.currentMapDetail.textContent = "确认选图后，页面会把它视为当前默认地图。";
      stateEls.currentMapBadge.className = "map-badge";
      stateEls.currentMapBadge.textContent = "未选择";
      return;
    }

    stateEls.currentMapTitle.textContent = selected.display_name || selected.map_id;
    if (startupRestoreHint) {
      stateEls.currentMapCard.className = "current-map-card current-map-card-restored";
      stateEls.currentMapDetail.textContent = "页面启动时已从后端恢复这张选中地图。";
      stateEls.currentMapBadge.className = "map-badge map-badge-selected";
      stateEls.currentMapBadge.textContent = "已恢复";
      return;
    }

    stateEls.currentMapCard.className = "current-map-card";
    stateEls.currentMapDetail.textContent = "当前后端会把这张地图作为默认选中地图。";
    stateEls.currentMapBadge.className = "map-badge map-badge-selected";
    stateEls.currentMapBadge.textContent = "当前使用";
  }

  function syncPendingSelection() {
    const selectedMapId = currentStatus && currentStatus.selected_map ? currentStatus.selected_map.map_id : "";
    if (selectedMapId && pendingMapId === selectedMapId) {
      pendingMapId = "";
      pendingMapName = "";
    }
    stateEls.pendingMapName.textContent = pendingMapName || "未选择";
    stateEls.confirmMapSelectButton.disabled = !pendingMapId;
  }

  function setPendingMap(mapId, displayName) {
    pendingMapId = mapId || "";
    pendingMapName = displayName || "";
    syncPendingSelection();
    refreshPreview();
    loadPreviewMeta();
    renderMaps(currentMaps);
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
      setFeedback("状态加载失败: " + error.message);
    }
  }

  async function pingSession() {
    try {
      await requestJson("/api/session/ping", {
        method: "POST",
        body: JSON.stringify({ session_id: sessionId }),
      });
    } catch (error) {
      setFeedback("会话心跳失败: " + error.message);
    }
  }

  async function loadMaps() {
    try {
      const { payload } = await requestJson("/api/maps");
      if (!payload.ok) return;
      currentMaps = Array.isArray(payload.maps) ? payload.maps : [];
      renderMaps(currentMaps);
    } catch (error) {
      setFeedback("地图列表加载失败: " + error.message);
    }
  }

  async function loadPreviewMeta() {
    try {
      const suffix = pendingMapId ? "?map_id=" + encodeURIComponent(pendingMapId) : "";
      const { payload } = await requestJson("/api/map-preview-meta" + suffix);
      if (!payload.ok) return;
      currentPreview = payload.preview || null;
      renderPreviewMeta(currentPreview);
    } catch (error) {
      setFeedback("地图预览信息加载失败: " + error.message);
    }
  }

  function renderStatus(status) {
    currentStatus = status;
    const selectedMap = getSelectedMap(status);
    if (!initialMapStateKnown) {
      startupRestoreHint = !!(selectedMap && selectedMap.map_id);
      initialMapStateKnown = true;
    }
    stateEls.runtimeState.textContent = status.runtime_state;
    stateEls.selectedMode.textContent = status.selected_mode;
    stateEls.armedState.textContent = status.armed ? "是" : "否";
    stateEls.estopState.textContent = status.estop_latched ? "已锁定" : "未锁定";
    stateEls.faultState.textContent = status.fault_active ? status.fault_reason || "故障激活" : "无";
    stateEls.controlSource.textContent = status.current_control_source;
    stateEls.selectedMapName.textContent = (selectedMap && selectedMap.display_name) || "未选择地图";
    stateEls.speedLevelLabel.textContent = String(status.speed_level);
    stateEls.speedLevelDisplay.textContent = String(status.speed_level);
    stateEls.lastUpdateLabel.textContent = humanNow();
    stateEls.lastActionLabel.textContent =
      status.last_action && status.last_action.action
        ? status.last_action.action + " · " + (status.last_action.code || "")
        : "暂无动作";

    stateEls.backendPill.textContent = "后端在线";
    stateEls.backendPill.className = "pill pill-ok";
    stateEls.rosPill.textContent = status.ros_connected ? "ROS 已连接" : "ROS 未连接";
    stateEls.rosPill.className = "pill " + (status.ros_connected ? "pill-ok" : "pill-danger");

    document.querySelectorAll(".mode-button[data-mode]").forEach((button) => {
      button.classList.toggle("active", button.dataset.mode === status.selected_mode);
    });

    stateEls.saveMapButton.hidden = !isMappingMode(status.selected_mode);
    stateEls.renameMapButton.disabled = !(selectedMap && selectedMap.map_id);
    renderCurrentMapCard(status);
    syncPendingSelection();

    if (status.last_action) {
      setFeedback(
        [
          "动作: " + status.last_action.action,
          "接受: " + String(status.last_action.accepted),
          "代码: " + status.last_action.code,
          "消息: " + status.last_action.message,
        ].join("\n")
      );
    }
  }

  function renderPreviewMeta(preview) {
    const mode = currentStatus ? currentStatus.selected_mode : "";
    if (!preview) {
      stateEls.mapPreviewMeta.textContent = "等待后端预览数据";
      return;
    }

    const parts = [];
    parts.push(preview.message || "地图预览");
    if (preview.updated_at) {
      parts.push("更新时间 " + humanTime(preview.updated_at));
    }
    if (preview.stale) {
      parts.push("预览过期");
    }
    if (!supportsMapPreview(mode)) {
      parts.push("当前模式正式版可折叠");
    }
    stateEls.mapPreviewMeta.textContent = parts.join(" · ");
    stateEls.saveMapButton.disabled = !preview.can_save;
  }

  function renderMaps(maps) {
    const selectedMapId = currentStatus && currentStatus.selected_map ? currentStatus.selected_map.map_id : "";
    stateEls.mapsList.innerHTML = "";
    if (!maps.length) {
      const li = document.createElement("li");
      li.textContent = "暂无已注册地图";
      stateEls.mapsList.appendChild(li);
      return;
    }

    maps.forEach((map) => {
      const li = document.createElement("li");
      const wrapper = document.createElement("div");
      wrapper.className = "map-item";

      const top = document.createElement("div");
      top.className = "map-item-top";

      const textBox = document.createElement("div");
      const title = document.createElement("span");
      title.className = "map-item-title";
      title.textContent = map.display_name || map.map_id;
      const meta = document.createElement("span");
      meta.className = "map-item-meta";
      meta.textContent = [map.map_id, "更新时间 " + humanTime(map.updated_at || map.created_at)]
        .filter(Boolean)
        .join(" · ");
      textBox.appendChild(title);
      textBox.appendChild(meta);

      const badges = document.createElement("div");
      badges.className = "map-badges";
      if (map.map_id === selectedMapId) {
        const badge = document.createElement("span");
        badge.className = "map-badge map-badge-selected";
        badge.textContent = "当前使用";
        badges.appendChild(badge);
      }
      if (map.map_id === pendingMapId) {
        const badge = document.createElement("span");
        badge.className = "map-badge map-badge-pending";
        badge.textContent = "待确认";
        badges.appendChild(badge);
      }
      if (!map.available) {
        const badge = document.createElement("span");
        badge.className = "map-badge";
        badge.textContent = "文件缺失";
        badges.appendChild(badge);
      }

      top.appendChild(textBox);
      top.appendChild(badges);

      const actions = document.createElement("div");
      actions.className = "map-item-actions";

      const pickButton = document.createElement("button");
      const isCurrentMap = map.map_id === selectedMapId;
      pickButton.type = "button";
      pickButton.className = "mini-button";
      if (isCurrentMap) {
        pickButton.textContent = "当前使用";
        pickButton.disabled = true;
        pickButton.title = "这张地图已经是当前使用地图，无需暂选";
      } else {
        pickButton.textContent = map.map_id === pendingMapId ? "已暂选" : "暂选";
        pickButton.disabled = !map.available;
        pickButton.addEventListener("click", () => {
          setPendingMap(map.map_id, map.display_name || map.map_id);
        });
      }

      const renameButton = document.createElement("button");
      renameButton.type = "button";
      renameButton.className = "mini-button";
      renameButton.textContent = "改名";
      renameButton.addEventListener("click", async () => {
        const nextName = window.prompt("请输入新的地图显示名称", map.display_name || map.map_id);
        if (!nextName) return;
        await renameMap(map.map_id, nextName);
      });

      actions.appendChild(pickButton);
      actions.appendChild(renameButton);

      wrapper.appendChild(top);
      wrapper.appendChild(actions);
      li.appendChild(wrapper);
      stateEls.mapsList.appendChild(li);
    });
  }

  async function postMode(mode) {
    try {
      const { payload } = await requestJson("/api/mode/select", {
        method: "POST",
        body: JSON.stringify({ mode }),
      });
      if (payload.status) {
        renderStatus(payload.status);
      }
      await loadPreviewMeta();
      refreshPreview();
      setFeedback(JSON.stringify(payload, null, 2));
    } catch (error) {
      setFeedback("模式请求失败: " + error.message);
    }
  }

  async function postAction(action) {
    try {
      const { payload } = await requestJson("/api/action", {
        method: "POST",
        body: JSON.stringify({ action }),
      });
      if (payload.status) {
        renderStatus(payload.status);
      }
      await loadPreviewMeta();
      refreshPreview();
      setFeedback(JSON.stringify(payload, null, 2));
    } catch (error) {
      setFeedback("动作请求失败: " + error.message);
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
      setFeedback("速度档位更新失败: " + error.message);
    }
  }

  async function saveMap() {
    const suggestedName = "地图_" + new Date().toLocaleString("zh-CN", { hour12: false }).replace(/[/: ]/g, "_");
    const displayName = window.prompt("请输入地图名称", suggestedName);
    if (!displayName) return;
    try {
      const { payload } = await requestJson("/api/maps/save", {
        method: "POST",
        body: JSON.stringify({ display_name: displayName }),
      });
      startupRestoreHint = false;
      if (payload.status) renderStatus(payload.status);
      pendingMapId = "";
      pendingMapName = "";
      await loadMaps();
      await loadPreviewMeta();
      refreshPreview();
      setFeedback(JSON.stringify(payload, null, 2));
    } catch (error) {
      setFeedback("地图保存失败: " + error.message);
    }
  }

  async function confirmMapSelection() {
    if (!pendingMapId) return;
    try {
      const { payload } = await requestJson("/api/maps/select", {
        method: "POST",
        body: JSON.stringify({ map_id: pendingMapId }),
      });
      startupRestoreHint = false;
      if (payload.status) renderStatus(payload.status);
      pendingMapId = "";
      pendingMapName = "";
      await loadMaps();
      await loadPreviewMeta();
      refreshPreview();
      setFeedback(JSON.stringify(payload, null, 2));
    } catch (error) {
      setFeedback("地图选择失败: " + error.message);
    }
  }

  async function renameMap(mapId, displayName) {
    try {
      const { payload } = await requestJson("/api/maps/rename", {
        method: "POST",
        body: JSON.stringify({ map_id: mapId, display_name: displayName }),
      });
      if (payload.status) renderStatus(payload.status);
      if (pendingMapId === mapId) {
        pendingMapName = displayName;
      }
      await loadMaps();
      await loadPreviewMeta();
      refreshPreview();
      setFeedback(JSON.stringify(payload, null, 2));
    } catch (error) {
      setFeedback("地图改名失败: " + error.message);
    }
  }

  async function renameCurrentMap() {
    const selected = currentStatus && currentStatus.selected_map ? currentStatus.selected_map : null;
    if (!selected || !selected.map_id) return;
    const displayName = window.prompt("请输入新的地图显示名称", selected.display_name || selected.map_id);
    if (!displayName) return;
    await renameMap(selected.map_id, displayName);
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
      setFeedback("手动摇杆请求失败: " + error.message);
    }
  }

  function getPreviewUrl() {
    lastPreviewStamp += 1;
    let url = "/api/map-preview?t=" + lastPreviewStamp;
    if (pendingMapId) {
      url += "&map_id=" + encodeURIComponent(pendingMapId);
    }
    return url;
  }

  function refreshPreview() {
    stateEls.mapPreviewImage.src = getPreviewUrl();
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

    joystick.stick.style.transform = "translate(calc(-50% + " + limitedX + "px), calc(-50% + " + limitedY + "px))";
    stateEls.forwardAxisLabel.textContent = joystick.forward.toFixed(2);
    stateEls.turnAxisLabel.textContent = joystick.turn.toFixed(2);
  }

  function resetJoystick(send) {
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
    await loadPreviewMeta();
    refreshPreview();
  });

  document.querySelectorAll(".mode-button[data-mode]").forEach((button) => {
    button.addEventListener("click", () => postMode(button.dataset.mode));
  });

  document.getElementById("start-button").addEventListener("click", () => postAction("START"));
  document.getElementById("safe-stop-button").addEventListener("click", () => postAction("SAFE_STOP"));
  document.getElementById("estop-button").addEventListener("click", () => postAction("ESTOP"));
  stateEls.saveMapButton.addEventListener("click", saveMap);
  stateEls.renameMapButton.addEventListener("click", renameCurrentMap);
  stateEls.confirmMapSelectButton.addEventListener("click", confirmMapSelection);

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
  setInterval(loadPreviewMeta, 2500);
  setInterval(refreshPreview, 2500);
  setInterval(() => {
    if (joystick.active) sendManualIntent();
  }, 120);

  loadStatus();
  loadMaps();
  loadPreviewMeta();
  pingSession();
  refreshPreview();
})();
