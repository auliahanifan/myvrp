import numpy as np

from src.models.hub_config import HubConfig, MultiHubConfig, SourceAssignmentConfig
from src.models.location import Depot, Hub
from src.models.order import Order
from src.models.vehicle import Vehicle, VehicleFleet
from src.solver.order_classifier import OrderClassifier
from src.solver.solver_context import SolverContext
from src.utils.hub_routing import MultiHubRoutingManager


def make_order(order_id: str, kota: str) -> Order:
    return Order(
        sale_order_id=order_id,
        delivery_date="2025-01-01",
        delivery_time="08:00-10:00",
        load_weight_in_kg=10.0,
        partner_id=f"P-{order_id}",
        display_name=f"Customer {order_id}",
        alamat=f"Address {order_id}",
        coordinates=(-6.2, 106.8),
        kota=kota,
    )


def build_context(mode: str = "zone_based") -> SolverContext:
    depot = Depot(name="Depot", coordinates=(-6.2, 106.8))
    multi_hub = MultiHubConfig(
        enabled=True,
        unassigned_zone_behavior="depot",
        hubs=[
            HubConfig(
                hub=Hub(name="Hub Utara", coordinates=(-6.1, 106.81)),
                hub_id="hub_utara",
                zones_via_hub=["JAKARTA UTARA"],
            )
        ],
        source_assignment=SourceAssignmentConfig(mode=mode, min_cost_advantage_percent=7.5),
    )
    orders = [
        make_order("O-1", "JAKARTA UTARA"),
        make_order("O-2", "JAKARTA SELATAN"),
    ]
    fleet = VehicleFleet(vehicle_types=[(Vehicle("Motor", 80, 1500), 2, False)])
    manager = MultiHubRoutingManager(multi_hub, depot)
    distance = np.zeros((3, 3))
    duration = np.zeros((3, 3))
    return SolverContext.build(
        orders=orders,
        fleet=fleet,
        depot=depot,
        multi_hub_config=multi_hub,
        hub_routing_manager=manager,
        full_distance_matrix=distance,
        full_duration_matrix=duration,
        config={},
    )


def test_order_classifier_uses_zone_based_routing():
    context = build_context(mode="zone_based")

    result = OrderClassifier().classify(context)

    assert result.orders_by_source["hub_utara"] == [context.orders[0]]
    assert result.orders_by_source["DEPOT"] == [context.orders[1]]
    assert any("DEPOT (direct): 1 orders" in line for line in result.summary_lines)


def test_order_classifier_uses_dynamic_assigner_for_dynamic_mode(monkeypatch):
    context = build_context(mode="dynamic")

    class FakeAssigner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def assign_orders(self, orders, zone_assignments):
            return {"DEPOT": [orders[0]], "hub_utara": [orders[1]]}

        def get_assignment_summary(self, orders, assignments):
            return {"assignment_mode": "dynamic", "cost_threshold_percent": 7.5}

    monkeypatch.setattr("src.solver.order_classifier.DynamicSourceAssigner", FakeAssigner)

    result = OrderClassifier().classify(context)

    assert result.orders_by_source["DEPOT"] == [context.orders[0]]
    assert result.orders_by_source["hub_utara"] == [context.orders[1]]
    assert any("Mode: dynamic" in line for line in result.summary_lines)


def test_order_classifier_falls_back_to_zone_classification_when_assigner_returns_empty(monkeypatch):
    context = build_context(mode="hybrid")

    class FakeAssigner:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def assign_orders(self, orders, zone_assignments):
            return {"DEPOT": [], "hub_utara": []}

        def get_assignment_summary(self, orders, assignments):
            return {"assignment_mode": "hybrid", "cost_threshold_percent": 7.5}

    monkeypatch.setattr("src.solver.order_classifier.DynamicSourceAssigner", FakeAssigner)

    result = OrderClassifier().classify(context)

    assert result.orders_by_source["hub_utara"] == [context.orders[0]]
    assert result.orders_by_source["DEPOT"] == [context.orders[1]]
