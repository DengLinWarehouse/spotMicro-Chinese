from __future__ import annotations

import json
import os
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .models import ActionResult


class BackendHttpServer(object):
    def __init__(self, backend, host: str = "0.0.0.0", port: int = 8765):
        self._backend = backend
        self._host = host
        self._port = int(port)
        self._server = None
        self._thread = None
        self._web_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "web"))

    def start(self):
        if self._server is not None:
            return
        handler_cls = self._build_handler()
        self._server = ThreadingHTTPServer((self._host, self._port), handler_cls)
        self._thread = threading.Thread(target=self._server.serve_forever, name="spotmicro-http-api", daemon=True)
        self._thread.start()

    def stop(self):
        if self._server is None:
            return
        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._server = None
        self._thread = None

    def _build_handler(self):
        backend = self._backend
        web_root = self._web_root

        class RequestHandler(BaseHTTPRequestHandler):
            server_version = "SpotMicroAppBackend/0.1"

            def do_OPTIONS(self):
                self.send_response(HTTPStatus.NO_CONTENT)
                self._send_cors_headers()
                self.end_headers()

            def do_GET(self):
                parsed = urlparse(self.path)
                path = parsed.path
                query = parse_qs(parsed.query)
                if path == "/":
                    return self._serve_static("index.html", "text/html; charset=utf-8")
                if path == "/app.css":
                    return self._serve_static("app.css", "text/css; charset=utf-8")
                if path == "/app.js":
                    return self._serve_static("app.js", "application/javascript; charset=utf-8")
                if path == "/api/status":
                    return self._json_response({"ok": True, "status": backend.get_status()})
                if path == "/api/maps":
                    status = backend.get_status()
                    selected_map = status.get("selected_map", {}) or {}
                    return self._json_response(
                        {
                            "ok": True,
                            "maps": backend.list_maps(),
                            "selected_map_id": selected_map.get("map_id", ""),
                        }
                    )
                if path == "/api/map-preview-meta":
                    requested_map_id = self._first_query_value(query, "map_id")
                    return self._json_response(
                        {"ok": True, "preview": backend.get_map_preview_info(requested_map_id=requested_map_id)}
                    )
                if path == "/api/map-preview":
                    requested_map_id = self._first_query_value(query, "map_id")
                    return self._map_preview_response(requested_map_id)
                return self._json_response({"ok": False, "error": "not_found"}, status=HTTPStatus.NOT_FOUND)

            def do_POST(self):
                payload = self._read_json()
                if payload is None:
                    return self._json_response({"ok": False, "error": "invalid_json"}, status=HTTPStatus.BAD_REQUEST)

                if self.path == "/api/session/ping":
                    session_id = str(payload.get("session_id", "")).strip()
                    if not session_id:
                        return self._json_response({"ok": False, "error": "missing_session_id"}, status=HTTPStatus.BAD_REQUEST)
                    backend.note_session_seen(session_id)
                    return self._json_response({"ok": True, "status": backend.get_status()})

                if self.path == "/api/mode/select":
                    mode = str(payload.get("mode", "")).strip()
                    if not mode:
                        return self._json_response({"ok": False, "error": "missing_mode"}, status=HTTPStatus.BAD_REQUEST)
                    try:
                        result = backend.select_mode(mode)
                    except Exception as exc:
                        return self._json_response(
                            {"ok": False, "error": "invalid_mode", "message": str(exc)},
                            status=HTTPStatus.BAD_REQUEST,
                        )
                    return self._action_response(result)

                if self.path == "/api/action":
                    action = str(payload.get("action", "")).strip()
                    if not action:
                        return self._json_response({"ok": False, "error": "missing_action"}, status=HTTPStatus.BAD_REQUEST)
                    try:
                        result = backend.dispatch_action(action)
                    except Exception as exc:
                        return self._json_response(
                            {"ok": False, "error": "invalid_action", "message": str(exc)},
                            status=HTTPStatus.BAD_REQUEST,
                        )
                    return self._action_response(result)

                if self.path == "/api/manual-intent":
                    session_id = str(payload.get("session_id", "")).strip()
                    if not session_id:
                        return self._json_response({"ok": False, "error": "missing_session_id"}, status=HTTPStatus.BAD_REQUEST)
                    try:
                        forward_axis = float(payload.get("forward_axis", 0.0))
                        turn_axis = float(payload.get("turn_axis", 0.0))
                    except Exception:
                        return self._json_response({"ok": False, "error": "invalid_axes"}, status=HTTPStatus.BAD_REQUEST)
                    accepted = backend.submit_manual_intent(forward_axis, turn_axis, session_id)
                    return self._json_response({"ok": accepted, "status": backend.get_status()})

                if self.path == "/api/speed-level":
                    if "speed_level" not in payload:
                        return self._json_response({"ok": False, "error": "missing_speed_level"}, status=HTTPStatus.BAD_REQUEST)
                    try:
                        speed_level = int(payload["speed_level"])
                    except Exception:
                        return self._json_response({"ok": False, "error": "invalid_speed_level"}, status=HTTPStatus.BAD_REQUEST)
                    result = backend.set_speed_level(speed_level)
                    return self._action_response(result)

                if self.path == "/api/maps/save":
                    display_name = str(payload.get("display_name", "")).strip()
                    if not display_name:
                        return self._json_response({"ok": False, "error": "missing_display_name"}, status=HTTPStatus.BAD_REQUEST)
                    result = backend.save_map(display_name)
                    return self._action_response(result)

                if self.path == "/api/maps/select":
                    map_id = str(payload.get("map_id", "")).strip()
                    if not map_id:
                        return self._json_response({"ok": False, "error": "missing_map_id"}, status=HTTPStatus.BAD_REQUEST)
                    result = backend.select_map(map_id)
                    return self._action_response(result)

                if self.path == "/api/maps/rename":
                    map_id = str(payload.get("map_id", "")).strip()
                    display_name = str(payload.get("display_name", "")).strip()
                    if not map_id:
                        return self._json_response({"ok": False, "error": "missing_map_id"}, status=HTTPStatus.BAD_REQUEST)
                    if not display_name:
                        return self._json_response({"ok": False, "error": "missing_display_name"}, status=HTTPStatus.BAD_REQUEST)
                    result = backend.rename_map(map_id, display_name)
                    return self._action_response(result)

                return self._json_response({"ok": False, "error": "not_found"}, status=HTTPStatus.NOT_FOUND)

            def log_message(self, format, *args):
                return

            def _read_json(self):
                content_length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
                try:
                    return json.loads(raw.decode("utf-8"))
                except Exception:
                    return None

            def _action_response(self, result: ActionResult):
                status_code = HTTPStatus.OK if result.accepted else HTTPStatus.CONFLICT
                return self._json_response(
                    {"ok": result.accepted, "result": result.to_dict(), "status": backend.get_status()},
                    status=status_code,
                )

            def _map_preview_response(self, requested_map_id: str = ""):
                status = backend.get_status()
                selected_map = status.get("selected_map", {}) or {}
                mode = status.get("selected_mode", "UNKNOWN")
                state = status.get("runtime_state", "UNKNOWN")
                fault_reason = status.get("fault_reason") or ""
                preview = backend.get_map_preview_info(requested_map_id=requested_map_id)
                preview_path = str(preview.get("image_path", "") or "")
                map_name = str(preview.get("map_name", "") or selected_map.get("display_name") or "未选择地图")
                subtitle = str(preview.get("message", "") or "预览占位图")
                if preview_path and os.path.isfile(preview_path):
                    return self._serve_binary_file(preview_path, self._guess_mime(preview_path))

                if fault_reason:
                    subtitle = "故障: %s" % fault_reason
                elif state == "ESTOP_LATCHED":
                    subtitle = "急停已锁定"

                svg = self._build_preview_svg(mode, state, map_name, subtitle)
                body = svg.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self._send_cors_headers()
                self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            @staticmethod
            def _first_query_value(query, key: str) -> str:
                values = query.get(key) or []
                if not values:
                    return ""
                return str(values[0] or "").strip()

            def _build_preview_svg(self, mode: str, state: str, map_name: str, subtitle: str) -> str:
                safe_mode = self._xml_escape(mode)
                safe_state = self._xml_escape(state)
                safe_map = self._xml_escape(map_name)
                safe_subtitle = self._xml_escape(subtitle)
                return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 640">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#f7f1e8"/>
      <stop offset="100%" stop-color="#e8ddd0"/>
    </linearGradient>
    <pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse">
      <path d="M 48 0 L 0 0 0 48" fill="none" stroke="#d3c5b4" stroke-width="1"/>
    </pattern>
  </defs>
  <rect width="960" height="640" fill="url(#bg)"/>
  <rect width="960" height="640" fill="url(#grid)" opacity="0.7"/>
  <circle cx="735" cy="140" r="90" fill="#ca5c36" opacity="0.14"/>
  <circle cx="220" cy="470" r="130" fill="#1f2428" opacity="0.06"/>
  <rect x="88" y="84" width="784" height="472" rx="28" fill="#fffaf3" stroke="#d8ccbd" stroke-width="2"/>
  <text x="128" y="168" fill="#1d2329" font-size="34" font-family="'Segoe UI Variable','Trebuchet MS','Noto Sans SC',sans-serif">SpotMicro 地图预览</text>
  <text x="128" y="214" fill="#6d5f53" font-size="20" font-family="'Segoe UI Variable','Trebuchet MS','Noto Sans SC',sans-serif">在真实地图图片链路接入之前，这张占位图用于验证预览通路。</text>
  <text x="128" y="320" fill="#8a7767" font-size="16" font-family="'Segoe UI Variable','Trebuchet MS','Noto Sans SC',sans-serif">当前模式</text>
  <text x="128" y="354" fill="#22292f" font-size="32" font-family="'Segoe UI Variable','Trebuchet MS',sans-serif">""" + safe_mode + """</text>
  <text x="128" y="428" fill="#8a7767" font-size="16" font-family="'Segoe UI Variable','Trebuchet MS','Noto Sans SC',sans-serif">运行状态</text>
  <text x="128" y="462" fill="#22292f" font-size="32" font-family="'Segoe UI Variable','Trebuchet MS',sans-serif">""" + safe_state + """</text>
  <text x="500" y="320" fill="#8a7767" font-size="16" font-family="'Segoe UI Variable','Trebuchet MS','Noto Sans SC',sans-serif">当前地图</text>
  <text x="500" y="354" fill="#22292f" font-size="32" font-family="'Segoe UI Variable','Trebuchet MS',sans-serif">""" + safe_map + """</text>
  <text x="500" y="428" fill="#8a7767" font-size="16" font-family="'Segoe UI Variable','Trebuchet MS','Noto Sans SC',sans-serif">说明</text>
  <text x="500" y="462" fill="#22292f" font-size="28" font-family="'Segoe UI Variable','Trebuchet MS',sans-serif">""" + safe_subtitle + """</text>
</svg>"""

            def _serve_static(self, filename: str, content_type: str):
                return self._serve_binary_file(os.path.join(web_root, filename), content_type)

            def _serve_binary_file(self, path: str, content_type: str):
                if not os.path.isfile(path):
                    return self._json_response({"ok": False, "error": "not_found"}, status=HTTPStatus.NOT_FOUND)
                with open(path, "rb") as handle:
                    body = handle.read()
                self.send_response(HTTPStatus.OK)
                self._send_cors_headers()
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)

            @staticmethod
            def _guess_mime(path: str) -> str:
                lower = path.lower()
                if lower.endswith(".png"):
                    return "image/png"
                if lower.endswith(".svg"):
                    return "image/svg+xml; charset=utf-8"
                if lower.endswith(".jpg") or lower.endswith(".jpeg"):
                    return "image/jpeg"
                return "application/octet-stream"

            @staticmethod
            def _xml_escape(value: str) -> str:
                return (
                    str(value)
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace('"', "&quot;")
                    .replace("'", "&apos;")
                )

            def _json_response(self, payload, status=HTTPStatus.OK):
                body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
                self.send_response(status)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_cors_headers(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "Content-Type")

        return RequestHandler
