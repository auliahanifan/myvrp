import numpy as np

from src.models.hub_config import HubConfig, MultiHubConfig
from src.models.location import Depot, Hub
from src.models.order import Order
from src.models.vehicle import Vehicle, VehicleFleet
from src.solver.matrix_slicer import MatrixSlicer
from src.solver.solver_context import SolverContext
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


def build_context() -> SolverContext:
    depot = Depot(name="Depot", coordinates=(-6.2, 106.8))
    hub_config = MultiHubConfig(
        enabled=True,
        hubs=[
            HubConfig(
                hub=Hub(name="Hub A", coordinates=(-6.1, 106.81)),
                hub_id="hub_a",
            )
        ],
    )
    orders = [
        make_order("O-1", -6.21, 106.83),
        make_order("O-2", -6.22, 106.84),
    ]
    fleet = VehicleFleet(vehicle_types=[(Vehicle("Motor", 80, 1500), 2, False)])
    manager = MultiHubRoutingManager(hub_config, depot)
    distance = np.arange(16).reshape(4, 4).astype(float)
    duration = np.arange(16).reshape(4, 4).astype(float)
    return SolverContext.build(
        orders=orders,
        fleet=fleet,
        depot=depot,
        multi_hub_config=hub_config,
        hub_routing_manager=manager,
        full_distance_matrix=distance,
        full_duration_matrix=duration,
        config={},
    )


def test_matrix_slicer_returns_depot_and_order_indices():
    context = build_context()
    slicer = MatrixSlicer(context)

    indices = slicer.get_depot_indices(context.orders)

    assert indices == [0, 2, 3]


def test_matrix_slicer_returns_hub_and_known_order_indices_only():
    context = build_context()
    slicer = MatrixSlicer(context)
    missing_order = make_order("MISSING", -6.23, 106.85)

    indices = slicer.get_hub_indices("hub_a", [context.orders[1], missing_order])

    assert indices == [1, 3]


def test_matrix_slicer_extracts_square_submatrix():
    context = build_context()
    slicer = MatrixSlicer(context)

    submatrix = slicer.extract(context.full_distance_matrix, [0, 2, 3])

    assert np.array_equal(
        submatrix,
        np.array(
            [
                [0.0, 2.0, 3.0],
                [8.0, 10.0, 11.0],
                [12.0, 14.0, 15.0],
            ]
        ),
    )


def test_matrix_slicer_preserves_duplicate_sale_order_ids_by_object_identity():
    depot = Depot(name="Depot", coordinates=(-6.2, 106.8))
    hub_config = MultiHubConfig(enabled=False)
    duplicated_orders = [
        make_order("O-DUP", -6.21, 106.83),
        make_order("O-DUP", -6.22, 106.84),
    ]
    fleet = VehicleFleet(vehicle_types=[(Vehicle("Motor", 80, 1500), 2, False)])
    manager = MultiHubRoutingManager(hub_config, depot)
    distance = np.arange(9).reshape(3, 3).astype(float)
    duration = np.arange(9).reshape(3, 3).astype(float)
    context = SolverContext.build(
        orders=duplicated_orders,
        fleet=fleet,
        depot=depot,
        multi_hub_config=hub_config,
        hub_routing_manager=manager,
        full_distance_matrix=distance,
        full_duration_matrix=duration,
        config={},
    )
    slicer = MatrixSlicer(context)

    indices = slicer.get_depot_indices(duplicated_orders)

    assert indices == [0, 1, 2]
