from __future__ import annotations

import binascii
from dataclasses import dataclass
from datetime import datetime
import json
import math
import os
from threading import RLock
import time
from typing import Dict, List, Optional, Tuple
import zlib

import rospy
from nav_msgs.msg import OccupancyGrid

from .models import ActionResult, ActionType, ControlMode
from .state_manager import StateManager


@dataclass(frozen=True)
class MapStorageConfig:
    root_dir: str
    maps_dir: str
    previews_dir: str
    registry_file: str
    preview_filename: str = "latest_preview.png"
    preview_max_side_px: int = 512
    preview_stale_after_sec: float = 8.0
    occupied_thresh: float = 0.65
    free_thresh: float = 0.196

    def expanded(self) -> "MapStorageConfig":
        return MapStorageConfig(
            root_dir=os.path.abspath(os.path.expanduser(self.root_dir)),
            maps_dir=os.path.abspath(os.path.expanduser(self.maps_dir)),
            previews_dir=os.path.abspath(os.path.expanduser(self.previews_dir)),
            registry_file=os.path.abspath(os.path.expanduser(self.registry_file)),
            preview_filename=self.preview_filename,
            preview_max_side_px=max(int(self.preview_max_side_px), 64),
            preview_stale_after_sec=max(float(self.preview_stale_after_sec), 1.0),
            occupied_thresh=float(self.occupied_thresh),
            free_thresh=float(self.free_thresh),
        )


@dataclass
class MapRecord:
    map_id: str
    display_name: str
    yaml_path: str = ""
    preview_path: str = ""
    created_at: float = 0.0
    updated_at: float = 0.0
    source: str = "manual_save"

    def to_dict(self) -> Dict[str, object]:
        return {
            "map_id": self.map_id,
            "display_name": self.display_name,
            "yaml_path": self.yaml_path,
            "preview_path": self.preview_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source,
            "available": self.is_available(),
        }

    def is_available(self) -> bool:
        return bool(self.yaml_path and os.path.isfile(self.yaml_path))

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "MapRecord":
        return cls(
            map_id=str(payload.get("map_id", "")),
            display_name=str(payload.get("display_name", "")),
            yaml_path=str(payload.get("yaml_path", "")),
            preview_path=str(payload.get("preview_path", "")),
            created_at=float(payload.get("created_at", 0.0) or 0.0),
            updated_at=float(payload.get("updated_at", 0.0) or 0.0),
            source=str(payload.get("source", "manual_save")),
        )


class MapRegistry(object):
    _MAPPING_MODES = (ControlMode.MANUAL_MAPPING, ControlMode.AUTO_EXPLORE_MAPPING)

    def __init__(self, state_manager: StateManager, storage_config: MapStorageConfig, map_topic: str, dry_run: bool):
        self._state_manager = state_manager
        self._config = storage_config.expanded()
        self._map_topic = str(map_topic or "/map")
        self._dry_run = bool(dry_run)
        self._lock = RLock()
        self._maps = {}

        self._latest_map = None
        self._latest_map_stamp = None
        self._latest_map_received_at = 0.0
        self._runtime_preview_stamp = None
        self._runtime_preview_updated_at = 0.0
        self._runtime_preview_path = os.path.join(self._config.previews_dir, self._config.preview_filename)

        self._ensure_storage_layout()
        self._load_registry()

        if not self._dry_run:
            self._map_sub = rospy.Subscriber(self._map_topic, OccupancyGrid, self._map_cb, queue_size=1)
        else:
            self._map_sub = None

    def list_maps(self) -> List[Dict[str, object]]:
        with self._lock:
            records = sorted(self._maps.values(), key=lambda item: (item.updated_at, item.created_at, item.map_id), reverse=True)
            return [record.to_dict() for record in records]

    def save_map(self, display_name: str, current_mode: ControlMode) -> ActionResult:
        clean_name = self._normalize_display_name(display_name)
        if not clean_name:
            return ActionResult(ActionType.SAVE_MAP, False, "invalid_name", "map display name cannot be empty")
        if current_mode not in self._MAPPING_MODES:
            return ActionResult(ActionType.SAVE_MAP, False, "mode_not_allowed", "map save is only allowed in mapping modes")

        with self._lock:
            if self._dry_run:
                return self._save_dry_run_map_locked(clean_name)
            if not self._has_valid_map_locked():
                return ActionResult(ActionType.SAVE_MAP, False, "no_map_data", "no valid runtime map is available yet")
            return self._save_live_map_locked(clean_name)

    def select_map(self, map_id: str) -> ActionResult:
        target_map_id = str(map_id or "").strip()
        if not target_map_id:
            return ActionResult(ActionType.SELECT_MAP, False, "missing_map_id", "map id is required")

        state = self._state_manager.snapshot()
        if state.armed:
            return ActionResult(ActionType.SELECT_MAP, False, "robot_armed", "cannot switch map while robot is armed")

        with self._lock:
            record = self._maps.get(target_map_id)
            if record is None:
                return ActionResult(ActionType.SELECT_MAP, False, "map_not_found", "requested map does not exist")
            if not record.is_available():
                return ActionResult(ActionType.SELECT_MAP, False, "map_unavailable", "requested map file is unavailable")

        self._state_manager.set_selected_map(record.map_id, record.display_name)
        return ActionResult(
            ActionType.SELECT_MAP,
            True,
            "map_selected",
            "map selection updated",
            {"map_id": record.map_id, "display_name": record.display_name},
        )

    def rename_map(self, map_id: str, display_name: str) -> ActionResult:
        target_map_id = str(map_id or "").strip()
        clean_name = self._normalize_display_name(display_name)
        if not target_map_id:
            return ActionResult(ActionType.RENAME_MAP, False, "missing_map_id", "map id is required")
        if not clean_name:
            return ActionResult(ActionType.RENAME_MAP, False, "invalid_name", "map display name cannot be empty")

        with self._lock:
            record = self._maps.get(target_map_id)
            if record is None:
                return ActionResult(ActionType.RENAME_MAP, False, "map_not_found", "requested map does not exist")
            record.display_name = clean_name
            record.updated_at = time.time()
            self._persist_registry_locked()

        state = self._state_manager.snapshot()
        if state.selected_map.map_id == target_map_id:
            self._state_manager.set_selected_map(target_map_id, clean_name)

        return ActionResult(
            ActionType.RENAME_MAP,
            True,
            "map_renamed",
            "map display name updated",
            {"map_id": target_map_id, "display_name": clean_name},
        )

    def get_preview_info(self, current_mode: ControlMode, selected_map_id: str = "", requested_map_id: str = "") -> Dict[str, object]:
        with self._lock:
            info = {
                "available": False,
                "image_path": "",
                "updated_at": 0.0,
                "stale": False,
                "source": "placeholder",
                "mode": current_mode.value,
                "map_id": "",
                "map_name": "",
                "message": "等待地图预览",
                "can_save": current_mode in self._MAPPING_MODES and (self._dry_run or self._has_valid_map_locked()),
            }

            if requested_map_id:
                record = self._maps.get(requested_map_id)
                if record is not None and record.preview_path and os.path.isfile(record.preview_path):
                    info.update(
                        {
                            "available": True,
                            "image_path": record.preview_path,
                            "updated_at": record.updated_at or record.created_at,
                            "source": "saved_map",
                            "map_id": record.map_id,
                            "map_name": record.display_name,
                            "message": "待确认地图预览",
                            "can_save": False,
                        }
                    )
                    return info

            if current_mode in self._MAPPING_MODES:
                if self._ensure_runtime_preview_locked():
                    stale = (time.time() - self._latest_map_received_at) > self._config.preview_stale_after_sec
                    selected_name = self._state_manager.snapshot().selected_map.display_name
                    info.update(
                        {
                            "available": True,
                            "image_path": self._runtime_preview_path,
                            "updated_at": self._runtime_preview_updated_at,
                            "stale": stale,
                            "source": "runtime",
                            "map_id": selected_map_id,
                            "map_name": selected_name,
                            "message": "建图预览%s" % ("（预览过期）" if stale else "已更新"),
                        }
                    )
                    return info
                if self._dry_run:
                    self._write_placeholder_preview_locked()
                    info.update(
                        {
                            "available": True,
                            "image_path": self._runtime_preview_path,
                            "updated_at": self._runtime_preview_updated_at,
                            "source": "dry_run",
                            "message": "dry-run 预览占位图",
                        }
                    )
                    return info
                info["message"] = "暂无可显示的建图预览"
                return info

            record = self._maps.get(selected_map_id or "")
            if record is not None and record.preview_path and os.path.isfile(record.preview_path):
                info.update(
                    {
                        "available": True,
                        "image_path": record.preview_path,
                        "updated_at": record.updated_at or record.created_at,
                        "source": "selected_map",
                        "map_id": record.map_id,
                        "map_name": record.display_name,
                        "message": "当前选中地图预览",
                    }
                )
                return info

            info["message"] = "当前模式暂无地图预览"
            return info

    def _ensure_storage_layout(self):
        os.makedirs(self._config.root_dir, exist_ok=True)
        os.makedirs(self._config.maps_dir, exist_ok=True)
        os.makedirs(self._config.previews_dir, exist_ok=True)

    def _load_registry(self):
        if not os.path.isfile(self._config.registry_file):
            return
        try:
            with open(self._config.registry_file, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception:
            return

        maps = payload.get("maps", []) if isinstance(payload, dict) else []
        for item in maps:
            try:
                record = MapRecord.from_dict(item)
            except Exception:
                continue
            if record.map_id:
                self._maps[record.map_id] = record

    def _persist_registry_locked(self):
        payload = {
            "maps": [record.to_dict() for record in sorted(self._maps.values(), key=lambda item: item.map_id)],
            "updated_at": time.time(),
        }
        with open(self._config.registry_file, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2)

    def _map_cb(self, msg: OccupancyGrid):
        with self._lock:
            self._latest_map = msg
            self._latest_map_stamp = (int(msg.header.stamp.secs), int(msg.header.stamp.nsecs))
            self._latest_map_received_at = time.time()

    def _has_valid_map_locked(self) -> bool:
        if self._latest_map is None:
            return False
        return bool(self._latest_map.info.width > 0 and self._latest_map.info.height > 0 and self._latest_map.data)

    def _ensure_runtime_preview_locked(self) -> bool:
        if not self._has_valid_map_locked():
            return False
        if self._runtime_preview_stamp == self._latest_map_stamp and os.path.isfile(self._runtime_preview_path):
            return True
        self._write_preview_png_from_map_locked(self._latest_map, self._runtime_preview_path)
        self._runtime_preview_stamp = self._latest_map_stamp
        self._runtime_preview_updated_at = time.time()
        return True

    def _save_live_map_locked(self, display_name: str) -> ActionResult:
        timestamp = time.time()
        map_id = self._new_map_id(timestamp)
        map_dir = os.path.join(self._config.maps_dir, map_id)
        os.makedirs(map_dir, exist_ok=True)

        base_path = os.path.join(map_dir, "map")
        preview_path = os.path.join(map_dir, "preview.png")
        self._write_map_yaml_and_pgm_locked(self._latest_map, base_path)
        self._write_preview_png_from_map_locked(self._latest_map, preview_path)

        record = MapRecord(
            map_id=map_id,
            display_name=display_name,
            yaml_path=base_path + ".yaml",
            preview_path=preview_path,
            created_at=timestamp,
            updated_at=timestamp,
            source="manual_save",
        )
        self._maps[record.map_id] = record
        self._persist_registry_locked()
        self._state_manager.set_selected_map(record.map_id, record.display_name)
        return ActionResult(
            ActionType.SAVE_MAP,
            True,
            "map_saved",
            "map snapshot saved successfully",
            {"map_id": record.map_id, "display_name": record.display_name, "yaml_path": record.yaml_path},
        )

    def _save_dry_run_map_locked(self, display_name: str) -> ActionResult:
        timestamp = time.time()
        map_id = self._new_map_id(timestamp)
        map_dir = os.path.join(self._config.maps_dir, map_id)
        os.makedirs(map_dir, exist_ok=True)

        base_path = os.path.join(map_dir, "map")
        preview_path = os.path.join(map_dir, "preview.png")
        self._write_placeholder_map_files_locked(base_path, preview_path)

        record = MapRecord(
            map_id=map_id,
            display_name=display_name,
            yaml_path=base_path + ".yaml",
            preview_path=preview_path,
            created_at=timestamp,
            updated_at=timestamp,
            source="dry_run_placeholder",
        )
        self._maps[record.map_id] = record
        self._persist_registry_locked()
        self._state_manager.set_selected_map(record.map_id, record.display_name)
        return ActionResult(
            ActionType.SAVE_MAP,
            True,
            "dry_run_map_saved",
            "dry-run placeholder map saved successfully",
            {"map_id": record.map_id, "display_name": record.display_name, "yaml_path": record.yaml_path},
        )

    def _write_map_yaml_and_pgm_locked(self, msg: OccupancyGrid, base_path: str):
        pgm_path = base_path + ".pgm"
        yaml_path = base_path + ".yaml"

        width = int(msg.info.width)
        height = int(msg.info.height)
        data = msg.data

        with open(pgm_path, "wb") as pgm:
            header = "P5\n# CREATOR: spot_micro_app_backend %.3f m/pix\n%d %d\n255\n" % (
                msg.info.resolution,
                width,
                height,
            )
            pgm.write(header.encode("ascii"))
            for y in range(height):
                row = height - y - 1
                for x in range(width):
                    value = data[row * width + x]
                    pgm.write(bytes((self._occupancy_to_pixel(value),)))

        yaw = self._yaw_from_quaternion(msg.info.origin.orientation)
        with open(yaml_path, "w", encoding="ascii") as yaml_file:
            yaml_file.write("image: %s\n" % os.path.basename(pgm_path))
            yaml_file.write("resolution: %.12g\n" % msg.info.resolution)
            yaml_file.write(
                "origin: [%.12g, %.12g, %.12g]\n" % (msg.info.origin.position.x, msg.info.origin.position.y, yaw)
            )
            yaml_file.write("negate: 0\n")
            yaml_file.write("occupied_thresh: %.3f\n" % self._config.occupied_thresh)
            yaml_file.write("free_thresh: %.3f\n" % self._config.free_thresh)

    def _write_preview_png_from_map_locked(self, msg: OccupancyGrid, path: str):
        width = int(msg.info.width)
        height = int(msg.info.height)
        max_side = max(int(self._config.preview_max_side_px), 64)
        stride = max(1, int(math.ceil(max(width, height) / float(max_side))))
        out_width = max(1, int(math.ceil(width / float(stride))))
        out_height = max(1, int(math.ceil(height / float(stride))))
        pixels = bytearray(out_width * out_height)

        write_index = 0
        for out_y in range(out_height):
            source_y = min(height - 1, out_y * stride)
            row = height - source_y - 1
            for out_x in range(out_width):
                source_x = min(width - 1, out_x * stride)
                value = msg.data[row * width + source_x]
                pixels[write_index] = self._occupancy_to_pixel(value)
                write_index += 1

        self._write_grayscale_png(path, out_width, out_height, bytes(pixels))

    def _write_placeholder_preview_locked(self):
        pixels = self._placeholder_pixels(160, 160)
        self._write_grayscale_png(self._runtime_preview_path, 160, 160, pixels)
        self._runtime_preview_updated_at = time.time()

    def _write_placeholder_map_files_locked(self, base_path: str, preview_path: str):
        width = 128
        height = 128
        pixels = self._placeholder_pixels(width, height)
        pgm_path = base_path + ".pgm"
        yaml_path = base_path + ".yaml"

        with open(pgm_path, "wb") as pgm:
            pgm.write(("P5\n# CREATOR: spot_micro_app_backend dry_run\n%d %d\n255\n" % (width, height)).encode("ascii"))
            pgm.write(pixels)

        with open(yaml_path, "w", encoding="ascii") as yaml_file:
            yaml_file.write("image: %s\n" % os.path.basename(pgm_path))
            yaml_file.write("resolution: 0.05\n")
            yaml_file.write("origin: [0.0, 0.0, 0.0]\n")
            yaml_file.write("negate: 0\n")
            yaml_file.write("occupied_thresh: %.3f\n" % self._config.occupied_thresh)
            yaml_file.write("free_thresh: %.3f\n" % self._config.free_thresh)

        self._write_grayscale_png(preview_path, width, height, pixels)

    @staticmethod
    def _write_grayscale_png(path: str, width: int, height: int, pixels: bytes):
        def chunk(tag: bytes, payload: bytes) -> bytes:
            return (
                len(payload).to_bytes(4, "big")
                + tag
                + payload
                + (binascii.crc32(tag + payload) & 0xFFFFFFFF).to_bytes(4, "big")
            )

        rows = bytearray()
        for row_index in range(height):
            start = row_index * width
            rows.append(0)
            rows.extend(pixels[start : start + width])

        header = b"\x89PNG\r\n\x1a\n"
        ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + bytes((8, 0, 0, 0, 0))
        idat = zlib.compress(bytes(rows), 9)
        body = header + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")
        with open(path, "wb") as handle:
            handle.write(body)

    @staticmethod
    def _placeholder_pixels(width: int, height: int) -> bytes:
        pixels = bytearray(width * height)
        for y in range(height):
            for x in range(width):
                idx = y * width + x
                grid = 232 if (x % 16 == 0 or y % 16 == 0) else 248
                if 18 < x < width - 18 and 18 < y < height - 18 and ((x + y) % 29 < 6):
                    grid = 170
                pixels[idx] = grid
        return bytes(pixels)

    def _new_map_id(self, timestamp: float) -> str:
        return "map_%s_%03d" % (
            datetime.fromtimestamp(timestamp).strftime("%Y%m%d_%H%M%S"),
            int((timestamp - math.floor(timestamp)) * 1000.0),
        )

    @staticmethod
    def _normalize_display_name(display_name: str) -> str:
        return " ".join(str(display_name or "").strip().split())

    def _occupancy_to_pixel(self, value: int) -> int:
        if value < 0:
            return 205
        if value >= int(self._config.occupied_thresh * 100.0):
            return 0
        if value <= int(self._config.free_thresh * 100.0):
            return 254
        return 205

    @staticmethod
    def _yaw_from_quaternion(quat) -> float:
        siny_cosp = 2.0 * (quat.w * quat.z + quat.x * quat.y)
        cosy_cosp = 1.0 - 2.0 * (quat.y * quat.y + quat.z * quat.z)
        return math.atan2(siny_cosp, cosy_cosp)

