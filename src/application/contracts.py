from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.models.hub_config import MultiHubConfig
from src.models.location import Depot
from src.models.order import Order
from src.models.route import RoutingSolution
from src.models.vehicle import VehicleFleet


@dataclass
class DebugOptions:
    debug_mode: bool = False
    save_distance_matrix: bool = False


@dataclass
class UploadOrdersResult:
    orders: list[Order]
    preview_rows: list[dict[str, Any]]
    total_orders: int
    total_weight_kg: float
    priority_orders: int


@dataclass
class RoutePlanSummary:
    total_vehicles: int
    total_orders: int
    total_distance_km: float
    total_cost: float
    computation_time_seconds: float
    optimization_strategy: str
    unassigned_orders: int


@dataclass
class AppConfigSnapshot:
    fleet: VehicleFleet
    vehicle_config: dict[str, Any]
    depot: Depot
    hubs_config: MultiHubConfig
    cache_config: dict[str, Any]
    solver_config: dict[str, Any]


@dataclass
class RoutePlanningRequest:
    orders_file_bytes: bytes
    orders_filename: str
    vehicle_config: dict[str, Any]
    optimization_strategy: str
    time_limit_seconds: int
    debug_options: DebugOptions = field(default_factory=DebugOptions)


@dataclass
class RoutePlanningResult:
    solution: RoutingSolution
    summary: RoutePlanSummary
    excel_path: Optional[Path]
    csv_path: Optional[Path]
    csv_summary_path: Optional[Path]
    hub_summary: dict[str, Any]
    depot: Depot
    hubs_config: MultiHubConfig
    map_cache_seed: str


@dataclass
class MapRenderRequest:
    solution: RoutingSolution
    selected_route_index: Optional[int]
    depot: Depot
    hubs_config: MultiHubConfig
    cache_key: str


@dataclass
class MapRenderResult:
    html: str
    cache_key: str
    generated_with_road_routing: bool


@dataclass
class HistoricalResultItem:
    filename: str
    created_at: datetime
    size_kb: float
    path: Path
