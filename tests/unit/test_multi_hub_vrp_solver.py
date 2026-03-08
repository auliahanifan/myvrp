import numpy as np
import pytest

from src.models.hub_config import HubConfig, MultiHubConfig
from src.models.location import Depot, Hub
from src.models.order import Order
from src.models.route import Route, RoutingSolution
from src.models.vehicle import Vehicle, VehicleFleet
from src.solver.order_classifier import ClassificationResult
from src.solver.tier1_blind_van_service import Tier1BlindVanService
from src.solver.two_tier_vrp_solver import MultiHubVRPSolver, TwoTierRoutingError, TwoTierVRPSolver
from src.utils.hub_routing import MultiHubRoutingManager


def make_order(order_id: str) -> Order:
    return Order(
        sale_order_id=order_id,
        delivery_date="2025-01-01",
        delivery_time="08:00-10:00",
        load_weight_in_kg=10.0,
        partner_id=f"P-{order_id}",
        display_name=f"Customer {order_id}",
        alamat=f"Address {order_id}",
        coordinates=(-6.2, 106.8),
        kota="JAKARTA",
    )


def build_solver(enabled: bool = True) -> MultiHubVRPSolver:
    depot = Depot(name="Depot", coordinates=(-6.2, 106.8))
    multi_hub = MultiHubConfig(
        enabled=enabled,
        hubs=[
            HubConfig(
                hub=Hub(name="Hub Utara", coordinates=(-6.1, 106.81)),
                hub_id="hub_utara",
            )
        ] if enabled else [],
    )
    orders = [make_order("O-1"), make_order("O-2")]
    fleet = VehicleFleet(
        vehicle_types=[
            (Vehicle("Blind Van", 500, 5000), 1, False),
            (Vehicle("Motor", 80, 1500), 2, False),
        ]
    )
    manager = MultiHubRoutingManager(multi_hub, depot)
    matrix_size = 1 + len(multi_hub.hubs) + len(orders)
    distance = np.zeros((matrix_size, matrix_size))
    duration = np.zeros((matrix_size, matrix_size))
    return MultiHubVRPSolver(
        orders=orders,
        fleet=fleet,
        depot=depot,
        multi_hub_config=multi_hub,
        hub_routing_manager=manager,
        full_distance_matrix=distance,
        full_duration_matrix=duration,
        config={"routing": {}},
    )


def make_route(vehicle_name: str, source: str) -> Route:
    return Route(
        vehicle=Vehicle(name=vehicle_name, capacity=80, cost_per_km=1500),
        source=source,
    )


def test_two_tier_alias_is_preserved():
    assert TwoTierVRPSolver is MultiHubVRPSolver


def test_multi_hub_solver_uses_zero_hub_path(monkeypatch):
    solver = build_solver(enabled=False)
    expected = RoutingSolution(routes=[make_route("Motor_0", "DEPOT")], unassigned_orders=[])

    class FakeClassifier:
        def classify(self, context):
            return ClassificationResult(orders_by_source={"DEPOT": context.orders}, summary_lines=["summary"])

    class FakeTier2Router:
        def solve_zero_hub(self, context, optimization_strategy, time_limit):
            assert optimization_strategy == "minimize_cost"
            assert time_limit == 90
            return expected

    monkeypatch.setattr("src.solver.two_tier_vrp_solver.OrderClassifier", lambda: FakeClassifier())
    monkeypatch.setattr("src.solver.two_tier_vrp_solver.Tier2SourceRouter", lambda: FakeTier2Router())

    solution = solver.solve(optimization_strategy="minimize_cost", time_limit=90)

    assert solution is expected


def test_multi_hub_solver_merges_tier1_and_tier2_results(monkeypatch):
    solver = build_solver(enabled=True)
    tier1_route = make_route("Blind Van_0", "DEPOT")
    tier2_route = make_route("DEPOT-Motor_0", "DEPOT")

    class FakeClassifier:
        def classify(self, context):
            return ClassificationResult(
                orders_by_source={"DEPOT": list(context.orders), "hub_utara": []},
                summary_lines=["summary"],
            )

    class FakeTier1Result:
        routes = [tier1_route]
        delivered_en_route_order_ids = {solver.orders[0].sale_order_id}
        log_lines = []

    class FakeTier1Service:
        def solve(self, context, classification, time_limit):
            return FakeTier1Result()

    class FakeAllocator:
        def allocate(self, context, orders_by_source):
            assert orders_by_source["DEPOT"] == [solver.orders[1]]
            return {"DEPOT": context.fleet}

    class FakeTier2Result:
        routes = [tier2_route]
        unassigned_orders = [solver.orders[0]]
        next_vehicle_offset = 2
        log_lines = []

    class FakeTier2Router:
        def solve_all_sources(self, **kwargs):
            assert kwargs["optimization_strategy"] == "balanced"
            return FakeTier2Result()

    monkeypatch.setattr("src.solver.two_tier_vrp_solver.OrderClassifier", lambda: FakeClassifier())
    monkeypatch.setattr("src.solver.two_tier_vrp_solver.Tier1BlindVanService", lambda: FakeTier1Service())
    monkeypatch.setattr("src.solver.two_tier_vrp_solver.VehicleAllocator", lambda: FakeAllocator())
    monkeypatch.setattr("src.solver.two_tier_vrp_solver.Tier2SourceRouter", lambda: FakeTier2Router())

    solution = solver.solve(optimization_strategy="balanced", time_limit=60)

    assert solution.routes == [tier1_route, tier2_route]
    assert solution.unassigned_orders == [solver.orders[0]]


def test_multi_hub_solver_wraps_internal_errors(monkeypatch):
    solver = build_solver(enabled=True)

    class FakeClassifier:
        def classify(self, context):
            raise RuntimeError("boom")

    monkeypatch.setattr("src.solver.two_tier_vrp_solver.OrderClassifier", lambda: FakeClassifier())

    with pytest.raises(TwoTierRoutingError, match="boom"):
        solver.solve()


def test_tier1_service_skips_when_no_hub_orders():
    solver = build_solver(enabled=True)
    classification = ClassificationResult(
        orders_by_source={"DEPOT": solver.orders},
        summary_lines=[],
    )

    result = Tier1BlindVanService().solve(solver.context, classification, time_limit=30)

    assert result.routes == []
    assert result.delivered_en_route_order_ids == set()


def test_tier1_service_skips_when_blind_van_missing():
    solver = build_solver(enabled=True)
    solver.context.fleet = VehicleFleet(vehicle_types=[(Vehicle("Motor", 80, 1500), 2, False)])
    classification = ClassificationResult(
        orders_by_source={"hub_utara": [solver.orders[0]], "DEPOT": [solver.orders[1]]},
        summary_lines=[],
    )

    result = Tier1BlindVanService().solve(solver.context, classification, time_limit=30)

    assert result.routes == []
    assert result.delivered_en_route_order_ids == set()
