import numpy as np

from src.models.hub_config import HubConfig, MultiHubConfig
from src.models.location import Depot, Hub
from src.models.order import Order
from src.models.route import Route, RoutingSolution
from src.models.vehicle import Vehicle, VehicleFleet
from src.solver.order_classifier import ClassificationResult
from src.solver.solver_context import SolverContext
from src.solver.tier2_source_router import Tier2SourceRouter
from src.utils.hub_routing import MultiHubRoutingManager


def make_order(order_id: str, lat: float, lon: float) -> Order:
    return Order(
        sale_order_id=order_id,
        delivery_date="2025-01-01",
        delivery_time="08:00-10:00",
        load_weight_in_kg=10.0,
        partner_id=f"P-{order_id}",
        display_name=f"Customer {order_id}",
        alamat=f"Address {order_id}",
        coordinates=(lat, lon),
        kota="JAKARTA",
    )


def build_context(multiple_trips: bool = False, multi_trip_enabled: bool = False) -> SolverContext:
    depot = Depot(name="Depot", coordinates=(-6.2, 106.8))
    multi_hub = MultiHubConfig(
        enabled=True,
        hubs=[
            HubConfig(
                hub=Hub(name="Hub Utara", coordinates=(-6.1, 106.81)),
                hub_id="hub_utara",
            )
        ],
    )
    orders = [
        make_order("O-1", -6.21, 106.83),
        make_order("O-2", -6.22, 106.84),
    ]
    fleet = VehicleFleet(
        vehicle_types=[(Vehicle("Motor", 80, 1500), 3, False)],
        multiple_trips=multiple_trips,
    )
    manager = MultiHubRoutingManager(multi_hub, depot)
    distance = np.arange(16).reshape(4, 4).astype(float)
    duration = np.arange(16).reshape(4, 4).astype(float)
    return SolverContext.build(
        orders=orders,
        fleet=fleet,
        depot=depot,
        multi_hub_config=multi_hub,
        hub_routing_manager=manager,
        full_distance_matrix=distance,
        full_duration_matrix=duration,
        config={"routing": {"multi_trip": {"enabled": multi_trip_enabled}}},
    )


def make_route(vehicle_name: str = "Motor_0") -> Route:
    return Route(
        vehicle=Vehicle(name=vehicle_name, capacity=80, cost_per_km=1500),
        source="UNKNOWN",
    )


def test_tier2_router_uses_vrp_solver_and_propagates_strategy(monkeypatch):
    context = build_context(multiple_trips=False, multi_trip_enabled=False)
    classification = ClassificationResult(
        orders_by_source={"DEPOT": [context.orders[0]], "hub_utara": [context.orders[1]]},
        summary_lines=[],
    )
    allocations = {
        "DEPOT": context.fleet,
        "hub_utara": context.fleet,
    }
    calls = []

    class FakeVRPSolver:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs["depot"].name, kwargs.get("vehicle_id_offset", 0)))

        def solve(self, optimization_strategy, time_limit):
            calls.append(("solve", optimization_strategy, time_limit))
            return RoutingSolution(routes=[make_route()], unassigned_orders=[])

    monkeypatch.setattr("src.solver.tier2_source_router.VRPSolver", FakeVRPSolver)
    monkeypatch.setattr("src.solver.tier2_source_router.MultiTripSolver", None)

    result = Tier2SourceRouter().solve_all_sources(
        context=context,
        classification=classification,
        allocated_fleets=allocations,
        optimization_strategy="minimize_cost",
        time_limit=77,
        vehicle_offset=5,
    )

    assert calls == [
        ("init", "Depot", 5),
        ("solve", "minimize_cost", 77),
        ("init", "Hub Utara", 6),
        ("solve", "minimize_cost", 77),
    ]
    assert [route.source for route in result.routes] == ["DEPOT", "hub_utara"]
    assert [route.vehicle.name for route in result.routes] == ["DEPOT-Motor_0", "HUB_UTARA-Motor_0"]


def test_tier2_router_uses_multi_trip_solver_when_enabled(monkeypatch):
    context = build_context(multiple_trips=True, multi_trip_enabled=True)
    classification = ClassificationResult(
        orders_by_source={"DEPOT": [context.orders[0]]},
        summary_lines=[],
    )
    calls = []

    class FakeMultiTripSolver:
        def __init__(self, **kwargs):
            calls.append(("init", kwargs["depot"].name))

        def solve(self, optimization_strategy, time_limit, source):
            calls.append(("solve", optimization_strategy, time_limit, source))
            return RoutingSolution(routes=[make_route("Motor_7")], unassigned_orders=[])

    monkeypatch.setattr("src.solver.tier2_source_router.MultiTripSolver", FakeMultiTripSolver)
    monkeypatch.setattr("src.solver.tier2_source_router.VRPSolver", None)

    result = Tier2SourceRouter().solve_all_sources(
        context=context,
        classification=classification,
        allocated_fleets={"DEPOT": context.fleet},
        optimization_strategy="minimize_vehicles",
        time_limit=45,
        vehicle_offset=0,
    )

    assert calls == [
        ("init", "Depot"),
        ("solve", "minimize_vehicles", 45, "DEPOT"),
    ]
    assert result.routes[0].vehicle.name == "DEPOT-Motor_7"


def test_tier2_router_solve_zero_hub_uses_context_orders(monkeypatch):
    context = build_context(multiple_trips=False, multi_trip_enabled=False)
    context.multi_hub_config.enabled = False
    calls = []

    class FakeVRPSolver:
        def __init__(self, **kwargs):
            calls.append(("init", len(kwargs["orders"]), kwargs["depot"].name))

        def solve(self, optimization_strategy, time_limit):
            calls.append(("solve", optimization_strategy, time_limit))
            return RoutingSolution(routes=[make_route()], unassigned_orders=[])

    monkeypatch.setattr("src.solver.tier2_source_router.VRPSolver", FakeVRPSolver)

    solution = Tier2SourceRouter().solve_zero_hub(
        context=context,
        optimization_strategy="balanced",
        time_limit=12,
    )

    assert calls == [
        ("init", 2, "Depot"),
        ("solve", "balanced", 12),
    ]
    assert solution.routes[0].source == "DEPOT"
