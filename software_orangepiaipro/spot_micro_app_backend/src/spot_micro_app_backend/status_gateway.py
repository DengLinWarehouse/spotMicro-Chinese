from __future__ import annotations

from .state_manager import StateManager


class StatusGateway(object):
    def __init__(self, state_manager: StateManager):
        self._state_manager = state_manager

    def get_status(self):
        return self._state_manager.to_dict()
