import numpy as np

from src.models.hub_config import HubConfig, MultiHubConfig
from src.models.location import Depot, Hub
from src.models.order import Order
from src.models.vehicle import Vehicle, VehicleFleet
from src.solver.solver_context import SolverContext
from src.utils.hub_routing import MultiHubRoutingManager


def make_order(order_id: str, lat: float, lon: float, kota: str = "JAKARTA") -> Order:
    return Order(
        sale_order_id=order_id,
        delivery_date="2025-01-01",
        delivery_time="08:00-10:00",
        load_weight_in_kg=10.0,
        partner_id=f"P-{order_id}",
        display_name=f"Customer {order_id}",
        alamat=f"Address {order_id}",
        coordinates=(lat, lon),
        kota=kota,
    )


def test_solver_context_builds_index_maps():
    depot = Depot(name="Depot", coordinates=(-6.2, 106.8))
    hub_config = MultiHubConfig(
        enabled=True,
        hubs=[
            HubConfig(
                hub=Hub(name="Hub A", coordinates=(-6.1, 106.81)),
                hub_id="hub_a",
            ),
            HubConfig(
                hub=Hub(name="Hub B", coordinates=(-6.3, 106.82)),
                hub_id="hub_b",
            ),
        ],
    )
    orders = [
        make_order("O-1", -6.21, 106.83),
        make_order("O-2", -6.22, 106.84),
    ]
    fleet = VehicleFleet(vehicle_types=[(Vehicle("Motor", 80, 1500), 2, False)])
    manager = MultiHubRoutingManager(hub_config, depot)
    distance = np.zeros((5, 5))
    duration = np.zeros((5, 5))

    context = SolverContext.build(
        orders=orders,
        fleet=fleet,
        depot=depot,
        multi_hub_config=hub_config,
        hub_routing_manager=manager,
        full_distance_matrix=distance,
        full_duration_matrix=duration,
        config={"routing": {}},
    )

    assert context.index_manager.get_depot_index() == 0
    assert context.hub_index_map == {"hub_a": 1, "hub_b": 2}
    assert context.order_index_map == {"O-1": 3, "O-2": 4}
    assert context.order_position_map == {"O-1": 0, "O-2": 1}


def test_solver_context_resolves_orders_by_identity_and_id():
    depot = Depot(name="Depot", coordinates=(-6.2, 106.8))
    hub_config = MultiHubConfig(enabled=False)
    orders = [make_order("O-1", -6.21, 106.83)]
    fleet = VehicleFleet(vehicle_types=[(Vehicle("Motor", 80, 1500), 1, False)])
    manager = MultiHubRoutingManager(hub_config, depot)
    distance = np.zeros((2, 2))
    duration = np.zeros((2, 2))

    context = SolverContext.build(
        orders=orders,
        fleet=fleet,
        depot=depot,
        multi_hub_config=hub_config,
        hub_routing_manager=manager,
        full_distance_matrix=distance,
        full_duration_matrix=duration,
        config={},
    )

    duplicate_instance = make_order("O-1", -6.21, 106.83)

    assert context.resolve_order_position(orders[0]) == 0
    assert context.resolve_order_position(duplicate_instance) == 0
