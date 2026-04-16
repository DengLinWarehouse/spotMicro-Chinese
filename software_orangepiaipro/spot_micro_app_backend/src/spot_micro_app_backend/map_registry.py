from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .state_manager import StateManager


@dataclass
class MapRecord:
    map_id: str
    display_name: str
    yaml_path: str = ""
    preview_path: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "map_id": self.map_id,
            "display_name": self.display_name,
            "yaml_path": self.yaml_path,
            "preview_path": self.preview_path,
        }


class MapRegistry(object):
    def __init__(self, state_manager: StateManager):
        self._state_manager = state_manager
        self._maps = {}

    def list_maps(self) -> List[Dict[str, str]]:
        return [record.to_dict() for record in self._maps.values()]

    def register_map(self, map_id: str, display_name: str, yaml_path: str = "", preview_path: str = ""):
        self._maps[map_id] = MapRecord(map_id=map_id, display_name=display_name, yaml_path=yaml_path, preview_path=preview_path)

    def select_map(self, map_id: str) -> bool:
        record = self._maps.get(map_id)
        if record is None:
            return False
        self._state_manager.set_selected_map(record.map_id, record.display_name)
        return True
