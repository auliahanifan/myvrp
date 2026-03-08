from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import streamlit as st

from src.application.contracts import AppConfigSnapshot, RoutePlanningResult, UploadOrdersResult


@dataclass
class AppSessionState:
    upload_bytes: bytes | None = None
    upload_filename: str | None = None
    upload_result: UploadOrdersResult | None = None
    config_snapshot: AppConfigSnapshot | None = None
    vehicle_config: dict[str, Any] | None = None
    plan_result: RoutePlanningResult | None = None
    map_html_cache: dict[str, str] = field(default_factory=dict)
    config_modified: bool = False
    debug_mode: bool = False
    save_distance_matrix: bool = False


class StreamlitState:
    KEY = "app_state"

    @classmethod
    def get(cls) -> AppSessionState:
        if cls.KEY not in st.session_state:
            st.session_state[cls.KEY] = AppSessionState()
        return st.session_state[cls.KEY]

    @classmethod
    def initialize(cls, config_snapshot: AppConfigSnapshot) -> AppSessionState:
        state = cls.get()
        if state.config_snapshot is None:
            state.config_snapshot = config_snapshot
        if state.vehicle_config is None:
            state.vehicle_config = config_snapshot.vehicle_config
        return state
