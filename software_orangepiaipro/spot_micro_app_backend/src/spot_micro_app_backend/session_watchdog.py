from __future__ import annotations

import time

from .state_manager import StateManager


class SessionWatchdog(object):
    def __init__(self, state_manager: StateManager, manual_input_timeout_sec: float, session_timeout_sec: float):
        self._state_manager = state_manager
        self._manual_input_timeout_sec = max(float(manual_input_timeout_sec), 0.1)
        self._session_timeout_sec = max(float(session_timeout_sec), 0.1)

    def note_session_seen(self, session_id: str, timestamp_sec: float = None):
        if timestamp_sec is None:
            timestamp_sec = time.time()
        self._state_manager.mark_session_seen(session_id, timestamp_sec)

    def note_manual_input(self, session_id: str, timestamp_sec: float = None):
        if timestamp_sec is None:
            timestamp_sec = time.time()
        self._state_manager.mark_manual_input(session_id, timestamp_sec)

    def session_expired(self, now_sec: float = None) -> bool:
        state = self._state_manager.snapshot()
        if now_sec is None:
            now_sec = time.time()
        if state.last_session_seen_at <= 0.0:
            return True
        return (now_sec - state.last_session_seen_at) > self._session_timeout_sec

    def manual_input_expired(self, now_sec: float = None) -> bool:
        state = self._state_manager.snapshot()
        if now_sec is None:
            now_sec = time.time()
        if state.last_manual_input_at <= 0.0:
            return True
        return (now_sec - state.last_manual_input_at) > self._manual_input_timeout_sec
