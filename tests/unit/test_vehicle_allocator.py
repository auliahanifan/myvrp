import numpy as np

from src.models.hub_config import HubConfig, MultiHubConfig
from src.models.location import Depot, Hub
from src.models.order import Order
from src.models.vehicle import Vehicle, VehicleFleet
from src.solver.solver_context import SolverContext
from src.solver.vehicle_allocator import VehicleAllocator
from src.utils.hub_routing import MultiHubRoutingManager


def make_order(order_id: str, weight: float) -> Order:
    return Order(
        sale_order_id=order_id,
        delivery_date="2025-01-01",
        delivery_time="08:00-10:00",
        load_weight_in_kg=weight,
        partner_id=f"P-{order_id}",
        display_name=f"Customer {order_id}",
        alamat=f"Address {order_id}",
        coordinates=(-6.2, 106.8),
        kota="JAKARTA",
    )


def build_context() -> SolverContext:
    depot = Depot(name="Depot", coordinates=(-6.2, 106.8))
    multi_hub = MultiHubConfig(
        enabled=True,
        blind_van_vehicle_name="Blind Van",
        hubs=[
            HubConfig(
                hub=Hub(name="Hub Utara", coordinates=(-6.1, 106.81)),
                hub_id="hub_utara",
            )
        ],
    )
    orders = [
        make_order("O-1", 20.0),
        make_order("O-2", 80.0),
    ]
    fleet = VehicleFleet(
        vehicle_types=[
            (Vehicle("Blind Van", 500, 5000), 1, False),
            (Vehicle("Motor", 80, 1500), 4, False),
            (Vehicle("Backup Motor", 60, 1700), 0, True),
        ],
        multiple_trips=True,
        return_to_depot=False,
    )
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


def test_vehicle_allocator_splits_fixed_vehicles_proportionally():
    context = build_context()
    orders_by_source = {
        "DEPOT": [context.orders[0]],
        "hub_utara": [context.orders[1]],
    }

    allocations = VehicleAllocator().allocate(context, orders_by_source)

    depot_fleet = allocations["DEPOT"]
    hub_fleet = allocations["hub_utara"]
    assert depot_fleet.vehicle_types[0][0].name == "Motor"
    assert depot_fleet.vehicle_types[0][1] == 1
    assert hub_fleet.vehicle_types[0][1] == 3


def test_vehicle_allocator_excludes_blind_van_and_skips_empty_sources():
    context = build_context()
    orders_by_source = {
        "DEPOT": [context.orders[0], context.orders[1]],
        "hub_utara": [],
    }

    allocations = VehicleAllocator().allocate(context, orders_by_source)

    assert "hub_utara" not in allocations
    assert all(vehicle.name != "Blind Van" for vehicle, _, _ in allocations["DEPOT"].vehicle_types)


def test_vehicle_allocator_keeps_unlimited_vehicle_available_per_source():
    context = build_context()
    orders_by_source = {
        "DEPOT": [context.orders[0]],
        "hub_utara": [context.orders[1]],
    }

    allocations = VehicleAllocator().allocate(context, orders_by_source)

    for fleet in allocations.values():
        assert any(vehicle.name == "Backup Motor" and unlimited for vehicle, _, unlimited in fleet.vehicle_types)
