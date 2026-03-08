from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path

from src.models.location import Depot
from src.models.order import Order
from src.models.route import Route, RouteStop, RoutingSolution
from src.models.vehicle import Vehicle, VehicleFleet


def _make_order(
    sale_order_id: str = "SO-1",
    name: str = "Customer A",
    is_priority: bool = False,
) -> Order:
    return Order(
        sale_order_id=sale_order_id,
        delivery_date="2025-10-08",
        delivery_time="04:00-05:00",
        load_weight_in_kg=25.0,
        partner_id=f"P-{sale_order_id}",
        display_name=name,
        alamat=f"Address {name}",
        coordinates=(-6.21, 106.85),
        kota="Jakarta",
        kecamatan="Kebayoran",
        kelurahan="Senayan",
        is_priority=is_priority,
    )


def _make_fleet() -> VehicleFleet:
    return VehicleFleet(
        vehicle_types=[
            (
                Vehicle(
                    name="Motor",
                    capacity=80.0,
                    cost_per_km=2500.0,
                    fixed_cost=25000.0,
                ),
                2,
                False,
            )
        ],
        return_to_depot=True,
        priority_time_tolerance=5,
        non_priority_time_tolerance=30,
        multiple_trips=True,
        relax_time_windows=True,
        time_window_relaxation_minutes=15,
    )


def _make_solution() -> RoutingSolution:
    route = Route(
        vehicle=Vehicle(name="Motor", capacity=80.0, cost_per_km=2500.0),
        departure_time=210,
    )
    priority_order = _make_order("SO-2", "Priority Customer", is_priority=True)
    regular_order = _make_order("SO-3", "Regular Customer", is_priority=False)
    route.stops = [
        RouteStop(
            order=priority_order,
            arrival_time=240,
            departure_time=255,
            distance_from_prev=4.5,
            cumulative_weight=25.0,
            sequence=0,
        ),
        RouteStop(
            order=regular_order,
            arrival_time=270,
            departure_time=285,
            distance_from_prev=3.0,
            cumulative_weight=50.0,
            sequence=1,
        ),
    ]
    route.calculate_metrics()

    return RoutingSolution(
        routes=[route],
        unassigned_orders=[_make_order("SO-9", "Unassigned Customer")],
        optimization_strategy="balanced",
        computation_time=12.4,
    )


def test_configuration_service_round_trips_vehicle_config():
    from src.application.configuration_service import ConfigurationService

    service = ConfigurationService()
    fleet = _make_fleet()

    config_dict = service.fleet_to_config_dict(fleet)
    rebuilt_fleet = service.config_dict_to_fleet(config_dict)

    assert config_dict["vehicles"][0]["name"] == "Motor"
    assert rebuilt_fleet.return_to_depot is True
    assert rebuilt_fleet.relax_time_windows is True
    assert rebuilt_fleet.vehicle_types[0][0].name == "Motor"
    assert rebuilt_fleet.vehicle_types[0][1] == 2


def test_history_service_lists_latest_results_first(tmp_path: Path):
    from src.application.history_service import HistoryService

    older = tmp_path / "routing_result_older.xlsx"
    older.write_bytes(b"old")
    newer = tmp_path / "routing_result_newer.xlsx"
    newer.write_bytes(b"new")

    older_ts = datetime(2025, 10, 10, 8, 1, 9).timestamp()
    newer_ts = datetime(2025, 10, 10, 8, 40, 8).timestamp()

    older.touch()
    newer.touch()
    os.utime(older, (older_ts, older_ts))
    os.utime(newer, (newer_ts, newer_ts))

    items = HistoryService(results_dir=tmp_path).list_results()

    assert [item.filename for item in items] == [
        "routing_result_newer.xlsx",
        "routing_result_older.xlsx",
    ]


def test_results_service_builds_metrics_and_rows():
    from src.application.results_service import ResultsService

    depot = Depot("Main Depot", (-6.2088, 106.8456), "Jakarta")
    solution = _make_solution()

    service = ResultsService()
    metrics = service.build_summary_metrics(solution)
    route_rows = service.build_route_rows(solution, depot, hubs_config=None)
    unassigned_rows = service.build_unassigned_rows(solution)

    assert metrics["total_vehicles"] == 1
    assert metrics["total_orders"] == 2
    assert route_rows[0]["Vehicle"] == "Motor"
    assert route_rows[0]["Priority"] == "✅"
    assert unassigned_rows[0]["Customer"] == "Unassigned Customer"


@dataclass
class _FakeRoutingManager:
    summary: dict

    def get_routing_summary(self, orders):
        return self.summary


@dataclass
class _FakeSolver:
    solution: RoutingSolution

    def solve(self, optimization_strategy: str, time_limit: int) -> RoutingSolution:
        assert optimization_strategy == "balanced"
        assert time_limit == 60
        return self.solution


class _FakeCSVParser:
    def __init__(self, csv_path: str):
        self.csv_path = csv_path

    def parse(self):
        return [_make_order("SO-10", "Uploaded Customer")]


class _FakeYAMLParser:
    def __init__(self, path: str):
        self.path = path

    def parse(self):
        return _make_fleet()

    def get_hubs_config(self):
        class _HubConfig:
            is_zero_hub_mode = True
            hubs = []

        return _HubConfig()

    def get_cache_config(self):
        return {"directory": ".cache", "ttl_hours": 24, "enabled": True}

    def get_config(self):
        return {"routing": {"multi_trip": {"enabled": True}}}


class _FakeDistanceCalculator:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def calculate_matrix(self, locations):
        size = len(locations)
        return [[0.0] * size for _ in range(size)], [[0.0] * size for _ in range(size)]

    def get_cache_stats(self):
        return {"cache_hits": 0, "api_calls": 1}


class _FakeExcelGenerator:
    def __init__(self, depot: Depot):
        self.depot = depot

    def generate(self, solution, output_dir: str):
        return Path(output_dir) / "routing_result_2025-10-10_08-40-08.xlsx"


class _FakeCSVGenerator:
    def __init__(self, depot: Depot, hubs_config=None):
        self.depot = depot
        self.hubs_config = hubs_config

    def generate(self, solution, output_dir: str, filename: str):
        return Path(output_dir) / f"{filename}.csv"

    def generate_summary_csv(self, solution, output_dir: str, filename: str):
        return Path(output_dir) / f"{filename}.csv"


def test_route_planning_service_orchestrates_full_pipeline(tmp_path: Path):
    from src.application.contracts import AppConfigSnapshot, DebugOptions, RoutePlanningRequest
    from src.application.route_planning_service import RoutePlanningService

    depot = Depot("Main Depot", (-6.2088, 106.8456), "Jakarta")
    config_snapshot = AppConfigSnapshot(
        fleet=_make_fleet(),
        vehicle_config={"vehicles": [], "routing": {}},
        depot=depot,
        hubs_config=_FakeYAMLParser("conf.yaml").get_hubs_config(),
        cache_config={"directory": ".cache", "ttl_hours": 24, "enabled": True},
        solver_config={"routing": {"multi_trip": {"enabled": True}}},
    )
    request = RoutePlanningRequest(
        orders_file_bytes=b"sale_order_id\nSO-10\n",
        orders_filename="orders.csv",
        vehicle_config=config_snapshot.vehicle_config,
        optimization_strategy="balanced",
        time_limit_seconds=60,
        debug_options=DebugOptions(),
    )
    solution = _make_solution()

    service = RoutePlanningService(
        csv_parser_cls=_FakeCSVParser,
        yaml_parser_cls=_FakeYAMLParser,
        distance_calculator_cls=_FakeDistanceCalculator,
        routing_manager_factory=lambda hubs_config, depot: _FakeRoutingManager(
            {"total_hub_orders": 0, "direct_orders_count": 1, "hub_percentage": 0.0}
        ),
        solver_factory=lambda **kwargs: _FakeSolver(solution),
        excel_generator_cls=_FakeExcelGenerator,
        csv_generator_cls=_FakeCSVGenerator,
        now_provider=lambda: datetime(2025, 10, 10, 8, 40, 8),
        results_dir=tmp_path,
    )

    result = service.plan(request, config_snapshot)

    assert result.solution is solution
    assert result.summary.total_orders == 2
    assert result.excel_path.name == "routing_result_2025-10-10_08-40-08.xlsx"
    assert result.csv_path.name == "routing_result_2025-10-10_08-40-08.csv"
    assert result.csv_summary_path.name == "routing_summary_2025-10-10_08-40-08.csv"
    assert result.hub_summary["direct_orders_count"] == 1
