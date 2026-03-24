"""Unit tests for VRP solver."""
import pytest
import numpy as np
from src.solver.vrp_solver import VRPSolver, VRPSolverError
from src.models.order import Order
from src.models.vehicle import Vehicle, VehicleFleet
from src.models.location import Depot
from src.models.route import RoutingSolution


class TestVRPSolver:
    """Test suite for VRPSolver class."""

    def _make_order(
        self,
        sale_order_id: str,
        weight: float,
        coordinates: tuple[float, float],
        delivery_time: str = "04:00-08:00",
        fragile_order_lines: tuple[str, ...] = (),
    ) -> Order:
        return Order(
            sale_order_id=sale_order_id,
            delivery_date="2025-10-08",
            delivery_time=delivery_time,
            load_weight_in_kg=weight,
            partner_id=f"P-{sale_order_id}",
            display_name=f"Customer {sale_order_id}",
            alamat=f"Address {sale_order_id}",
            coordinates=coordinates,
            fragile_order_lines=fragile_order_lines,
        )

    @pytest.fixture
    def sample_depot(self):
        """Create sample depot."""
        return Depot("Test Depot", (-6.2088, 106.8456))

    @pytest.fixture
    def sample_orders_small(self):
        """Create small set of sample orders (3 orders)."""
        return [
            Order(
                sale_order_id="O001",
                delivery_date="2025-10-08",
                delivery_time="04:00-05:00",
                load_weight_in_kg=50.0,
                partner_id="P001",
                display_name="Customer 1",
                alamat="Address 1",
                coordinates=(-6.2100, 106.8500),
                is_priority=False
            ),
            Order(
                sale_order_id="O002",
                delivery_date="2025-10-08",
                delivery_time="05:00-06:00",
                load_weight_in_kg=75.0,
                partner_id="P002",
                display_name="Customer 2",
                alamat="Address 2",
                coordinates=(-6.2200, 106.8600),
                is_priority=False
            ),
            Order(
                sale_order_id="O003",
                delivery_date="2025-10-08",
                delivery_time="06:00-07:00",
                load_weight_in_kg=30.0,
                partner_id="P003",
                display_name="Customer 3",
                alamat="Address 3",
                coordinates=(-6.2300, 106.8700),
                is_priority=True
            ),
        ]

    @pytest.fixture
    def sample_fleet(self):
        """Create sample vehicle fleet."""
        vehicles = [
            Vehicle(name="L300", capacity=800, cost_per_km=5000),
            Vehicle(name="Granmax", capacity=500, cost_per_km=3500),
            Vehicle(name="Pickup", capacity=300, cost_per_km=2500),
        ]
        return VehicleFleet(vehicle_types=vehicles, unlimited=True)

    @pytest.fixture
    def sample_distance_matrix_small(self):
        """Create small distance matrix (4x4: depot + 3 customers)."""
        return np.array([
            [0.0,  5.0,  10.0, 15.0],  # Depot to all
            [5.0,  0.0,  6.0,  12.0],  # Customer 1 to all
            [10.0, 6.0,  0.0,  8.0],   # Customer 2 to all
            [15.0, 12.0, 8.0,  0.0],   # Customer 3 to all
        ])

    @pytest.fixture
    def sample_duration_matrix_small(self):
        """Create small duration matrix (4x4: depot + 3 customers)."""
        return np.array([
            [0.0,  10.0, 20.0, 30.0],  # Depot to all
            [10.0, 0.0,  12.0, 25.0],  # Customer 1 to all
            [20.0, 12.0, 0.0,  15.0],  # Customer 2 to all
            [30.0, 25.0, 15.0, 0.0],   # Customer 3 to all
        ])

    def test_solver_initialization(self, sample_orders_small, sample_fleet, sample_depot,
                                   sample_distance_matrix_small, sample_duration_matrix_small):
        """Test solver initialization."""
        solver = VRPSolver(
            orders=sample_orders_small,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_small,
            duration_matrix=sample_duration_matrix_small
        )

        assert len(solver.orders) == 3
        assert len(solver.locations) == 4  # depot + 3 customers
        assert solver.depot == sample_depot

    def test_solver_invalid_matrix_dimensions(self, sample_orders_small, sample_fleet, sample_depot,
                                              sample_duration_matrix_small):
        """Test that solver raises error for mismatched matrix dimensions."""
        # Create wrong-sized matrix (3x3 instead of 4x4)
        wrong_matrix = np.zeros((3, 3))

        with pytest.raises(VRPSolverError) as exc_info:
            VRPSolver(
                orders=sample_orders_small,
                fleet=sample_fleet,
                depot=sample_depot,
                distance_matrix=wrong_matrix,
                duration_matrix=sample_duration_matrix_small
            )

        assert "doesn't match number of locations" in str(exc_info.value)

    def test_solver_solve_small_dataset(self, sample_orders_small, sample_fleet, sample_depot,
                                       sample_distance_matrix_small, sample_duration_matrix_small):
        """Test solving small dataset."""
        solver = VRPSolver(
            orders=sample_orders_small,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_small,
            duration_matrix=sample_duration_matrix_small
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        assert isinstance(solution, RoutingSolution)
        assert len(solution.routes) > 0
        assert solution.total_vehicles_used > 0
        assert solution.total_distance > 0
        assert solution.total_cost > 0

    def test_solver_all_strategies(self, sample_orders_small, sample_fleet, sample_depot,
                                   sample_distance_matrix_small, sample_duration_matrix_small):
        """Test all optimization strategies."""
        strategies = ["minimize_vehicles", "minimize_cost", "balanced"]

        for strategy in strategies:
            solver = VRPSolver(
                orders=sample_orders_small,
                fleet=sample_fleet,
                depot=sample_depot,
                distance_matrix=sample_distance_matrix_small,
                duration_matrix=sample_duration_matrix_small
            )

            solution = solver.solve(optimization_strategy=strategy, time_limit=30)
            assert isinstance(solution, RoutingSolution)
            assert solution.optimization_strategy == strategy

    def test_solver_capacity_constraint(self, sample_fleet, sample_depot,
                                       sample_distance_matrix_small, sample_duration_matrix_small):
        """Test that capacity constraints are enforced."""
        # Create orders that force multiple vehicles even with the largest 800kg vehicle.
        heavy_orders = [
            Order(
                sale_order_id="H001",
                delivery_date="2025-10-08",
                delivery_time="04:00-08:00",
                load_weight_in_kg=350.0,
                partner_id="P001",
                display_name="Heavy Customer 1",
                alamat="Address 1",
                coordinates=(-6.2100, 106.8500),
                is_priority=False
            ),
            Order(
                sale_order_id="H002",
                delivery_date="2025-10-08",
                delivery_time="04:00-08:00",
                load_weight_in_kg=350.0,
                partner_id="P002",
                display_name="Heavy Customer 2",
                alamat="Address 2",
                coordinates=(-6.2200, 106.8600),
                is_priority=False
            ),
            Order(
                sale_order_id="H003",
                delivery_date="2025-10-08",
                delivery_time="04:00-08:00",
                load_weight_in_kg=350.0,
                partner_id="P003",
                display_name="Heavy Customer 3",
                alamat="Address 3",
                coordinates=(-6.2300, 106.8700),
                is_priority=False
            ),
        ]

        solver = VRPSolver(
            orders=heavy_orders,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_small,
            duration_matrix=sample_duration_matrix_small
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        # Should use multiple vehicles since 3 x 350kg exceeds the largest 800kg vehicle.
        assert solution.total_vehicles_used >= 2

    def test_solver_time_window_validation(self, sample_orders_small, sample_fleet, sample_depot,
                                          sample_distance_matrix_small, sample_duration_matrix_small):
        """Test that time windows are respected in solution."""
        solver = VRPSolver(
            orders=sample_orders_small,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_small,
            duration_matrix=sample_duration_matrix_small
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        # Verify all stops are within their time windows
        for route in solution.routes:
            for stop in route.stops:
                order = stop.order
                arrival = stop.arrival_time

                # Arrival must be within time window
                assert arrival >= order.time_window_start, \
                    f"Order {order.sale_order_id} arrived too early"
                assert arrival <= order.time_window_end, \
                    f"Order {order.sale_order_id} arrived too late"

    def test_solver_single_order(self, sample_fleet, sample_depot):
        """Test solving with single order."""
        single_order = [
            Order(
                sale_order_id="SINGLE",
                delivery_date="2025-10-08",
                delivery_time="04:00-05:00",
                load_weight_in_kg=50.0,
                partner_id="P001",
                display_name="Single Customer",
                alamat="Address 1",
                coordinates=(-6.2100, 106.8500),
                is_priority=False
            ),
        ]

        # 2x2 matrix (depot + 1 customer)
        dist_matrix = np.array([[0.0, 5.0], [5.0, 0.0]])
        dur_matrix = np.array([[0.0, 10.0], [10.0, 0.0]])

        solver = VRPSolver(
            orders=single_order,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=dist_matrix,
            duration_matrix=dur_matrix
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        assert solution.total_vehicles_used == 1
        assert solution.total_orders_delivered == 1
        assert len(solution.unassigned_orders) == 0

    def test_solver_impossible_time_windows(self, sample_fleet, sample_depot):
        """Test handling of impossible time window constraints."""
        # Create orders with conflicting time windows (very tight windows far apart)
        impossible_orders = [
            Order(
                sale_order_id="I001",
                delivery_date="2025-10-08",
                delivery_time="04:00-04:01",  # 1 minute window
                load_weight_in_kg=50.0,
                partner_id="P001",
                display_name="Customer 1",
                alamat="Address 1",
                coordinates=(-6.2100, 106.8500),
                is_priority=False
            ),
            Order(
                sale_order_id="I002",
                delivery_date="2025-10-08",
                delivery_time="04:05-04:06",  # 1 minute window, 30 min drive away
                load_weight_in_kg=50.0,
                partner_id="P002",
                display_name="Customer 2",
                alamat="Address 2",
                coordinates=(-6.2200, 106.8600),
                is_priority=False
            ),
        ]

        # Matrix with 30 minute travel time
        dist_matrix = np.array([[0.0, 10.0, 20.0], [10.0, 0.0, 30.0], [20.0, 30.0, 0.0]])
        dur_matrix = np.array([[0.0, 20.0, 40.0], [20.0, 0.0, 60.0], [40.0, 60.0, 0.0]])

        solver = VRPSolver(
            orders=impossible_orders,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=dist_matrix,
            duration_matrix=dur_matrix
        )

        # With disjunctions, solver should still find a solution (may drop some orders)
        solution = solver.solve(optimization_strategy="balanced", time_limit=30)
        assert isinstance(solution, RoutingSolution)

        # Some orders may be unassigned due to impossible constraints
        # (with disjunctions enabled, solver can drop orders)

    def test_solver_computation_time(self, sample_orders_small, sample_fleet, sample_depot,
                                    sample_distance_matrix_small, sample_duration_matrix_small):
        """Test that computation time is tracked."""
        solver = VRPSolver(
            orders=sample_orders_small,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_small,
            duration_matrix=sample_duration_matrix_small
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        assert solution.computation_time > 0
        assert solution.computation_time < 30  # Should finish well within time limit

    def test_solver_route_metrics(self, sample_orders_small, sample_fleet, sample_depot,
                                  sample_distance_matrix_small, sample_duration_matrix_small):
        """Test that route metrics are calculated correctly."""
        solver = VRPSolver(
            orders=sample_orders_small,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_small,
            duration_matrix=sample_duration_matrix_small
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        # Verify solution-level metrics
        assert solution.total_vehicles_used == len(solution.routes)
        assert solution.total_orders_delivered <= len(sample_orders_small)

        # Verify route-level metrics
        for route in solution.routes:
            assert route.num_stops > 0
            assert route.total_distance > 0
            assert route.total_cost > 0
            assert route.total_weight > 0
            assert route.total_weight <= route.vehicle.capacity  # Capacity not exceeded

    def test_solver_mixed_motor_route_uses_80kg_when_fragile_present(self, sample_depot):
        """Fragile and non-fragile orders may share a motor route only under 80kg total."""
        orders = [
            self._make_order(
                sale_order_id="F001",
                weight=30.0,
                coordinates=(-6.2100, 106.8500),
                fragile_order_lines=("Telur",),
            ),
            self._make_order(
                sale_order_id="N001",
                weight=40.0,
                coordinates=(-6.2110, 106.8510),
            ),
        ]
        fleet = VehicleFleet(
            vehicle_types=[(Vehicle(name="Sepeda Motor", capacity=80, cost_per_km=1500), 1, False)]
        )
        dist_matrix = np.array([
            [0.0, 5.0, 6.0],
            [5.0, 0.0, 1.0],
            [6.0, 1.0, 0.0],
        ])
        dur_matrix = np.array([
            [0.0, 10.0, 11.0],
            [10.0, 0.0, 5.0],
            [11.0, 5.0, 0.0],
        ])

        solution = VRPSolver(
            orders=orders,
            fleet=fleet,
            depot=sample_depot,
            distance_matrix=dist_matrix,
            duration_matrix=dur_matrix,
            config={"constraints": {"enforce_city_limit": False}},
        ).solve(optimization_strategy="balanced", time_limit=10)

        assert solution.total_orders_delivered == 2
        assert len(solution.routes) == 1
        assert solution.routes[0].vehicle.capacity == 80
        assert solution.routes[0].total_weight == 70.0

    def test_solver_non_fragile_motor_route_can_use_120kg_variant(self, sample_depot):
        """Non-fragile-only motor routes may use the 120kg motor variant."""
        orders = [
            self._make_order(
                sale_order_id="N001",
                weight=55.0,
                coordinates=(-6.2100, 106.8500),
            ),
            self._make_order(
                sale_order_id="N002",
                weight=45.0,
                coordinates=(-6.2110, 106.8510),
            ),
        ]
        fleet = VehicleFleet(
            vehicle_types=[(Vehicle(name="Sepeda Motor", capacity=80, cost_per_km=1500), 1, False)]
        )
        dist_matrix = np.array([
            [0.0, 5.0, 6.0],
            [5.0, 0.0, 1.0],
            [6.0, 1.0, 0.0],
        ])
        dur_matrix = np.array([
            [0.0, 10.0, 11.0],
            [10.0, 0.0, 5.0],
            [11.0, 5.0, 0.0],
        ])

        solution = VRPSolver(
            orders=orders,
            fleet=fleet,
            depot=sample_depot,
            distance_matrix=dist_matrix,
            duration_matrix=dur_matrix,
            config={"constraints": {"enforce_city_limit": False}},
        ).solve(optimization_strategy="balanced", time_limit=10)

        assert solution.total_orders_delivered == 2
        assert len(solution.routes) == 1
        assert solution.routes[0].vehicle.capacity == 120
        assert solution.routes[0].total_weight == 100.0

    def test_solver_non_fragile_motor_route_uses_custom_max_capacity(self, sample_depot):
        """Non-fragile motor routes should honor per-motor max_capacity overrides."""
        orders = [
            self._make_order(
                sale_order_id="N001",
                weight=70.0,
                coordinates=(-6.2100, 106.8500),
            ),
            self._make_order(
                sale_order_id="N002",
                weight=60.0,
                coordinates=(-6.2110, 106.8510),
            ),
        ]
        fleet = VehicleFleet(
            vehicle_types=[
                (
                    Vehicle(
                        name="Sepeda Motor",
                        capacity=90,
                        max_capacity=140,
                        cost_per_km=1500,
                    ),
                    1,
                    False,
                )
            ]
        )
        dist_matrix = np.array([
            [0.0, 5.0, 6.0],
            [5.0, 0.0, 1.0],
            [6.0, 1.0, 0.0],
        ])
        dur_matrix = np.array([
            [0.0, 10.0, 11.0],
            [10.0, 0.0, 5.0],
            [11.0, 5.0, 0.0],
        ])

        solution = VRPSolver(
            orders=orders,
            fleet=fleet,
            depot=sample_depot,
            distance_matrix=dist_matrix,
            duration_matrix=dur_matrix,
            config={"constraints": {"enforce_city_limit": False}},
        ).solve(optimization_strategy="balanced", time_limit=10)

        assert solution.total_orders_delivered == 2
        assert len(solution.routes) == 1
        assert solution.routes[0].vehicle.capacity == 140
        assert solution.routes[0].total_weight == 130.0

    def test_solver_fragile_order_cannot_use_120kg_motor_variant(self, sample_depot):
        """Fragile orders should remain unassigned when only 120kg-equivalent motor fit exists."""
        orders = [
            self._make_order(
                sale_order_id="F001",
                weight=90.0,
                coordinates=(-6.2100, 106.8500),
                fragile_order_lines=("Telur",),
            ),
        ]
        fleet = VehicleFleet(
            vehicle_types=[(Vehicle(name="Sepeda Motor", capacity=80, cost_per_km=1500), 1, False)]
        )
        dist_matrix = np.array([[0.0, 5.0], [5.0, 0.0]])
        dur_matrix = np.array([[0.0, 10.0], [10.0, 0.0]])

        solution = VRPSolver(
            orders=orders,
            fleet=fleet,
            depot=sample_depot,
            distance_matrix=dist_matrix,
            duration_matrix=dur_matrix,
            config={"constraints": {"enforce_city_limit": False}},
        ).solve(optimization_strategy="balanced", time_limit=10)

        assert solution.total_orders_delivered == 0
        assert [order.sale_order_id for order in solution.unassigned_orders] == ["F001"]

    def test_solver_fragile_order_can_use_non_motor_vehicle(self, sample_depot):
        """Fragile orders may still be assigned to non-motor vehicles."""
        orders = [
            self._make_order(
                sale_order_id="F001",
                weight=90.0,
                coordinates=(-6.2100, 106.8500),
                fragile_order_lines=("Telur",),
            ),
        ]
        fleet = VehicleFleet(
            vehicle_types=[
                (Vehicle(name="City Car", capacity=250, cost_per_km=4000), 1, False),
                (Vehicle(name="Sepeda Motor", capacity=80, cost_per_km=1500), 1, False),
            ]
        )
        dist_matrix = np.array([[0.0, 5.0], [5.0, 0.0]])
        dur_matrix = np.array([[0.0, 10.0], [10.0, 0.0]])

        solution = VRPSolver(
            orders=orders,
            fleet=fleet,
            depot=sample_depot,
            distance_matrix=dist_matrix,
            duration_matrix=dur_matrix,
            config={"constraints": {"enforce_city_limit": False}},
        ).solve(optimization_strategy="balanced", time_limit=10)

        assert solution.total_orders_delivered == 1
        assert len(solution.routes) == 1
        assert solution.routes[0].vehicle.name.startswith("City Car")

    def test_solver_shared_motor_pool_prevents_using_both_variants(self, sample_depot):
        """One physical motor slot cannot be consumed by both 80kg and 120kg variants."""
        orders = [
            self._make_order(
                sale_order_id="F001",
                weight=50.0,
                coordinates=(-6.2100, 106.8500),
                delivery_time="04:00-04:15",
                fragile_order_lines=("Telur",),
            ),
            self._make_order(
                sale_order_id="N001",
                weight=50.0,
                coordinates=(-6.2500, 106.8900),
                delivery_time="04:00-04:15",
            ),
        ]
        fleet = VehicleFleet(
            vehicle_types=[(Vehicle(name="Sepeda Motor", capacity=80, cost_per_km=1500), 1, False)]
        )
        dist_matrix = np.array([
            [0.0, 5.0, 20.0],
            [5.0, 0.0, 20.0],
            [20.0, 20.0, 0.0],
        ])
        dur_matrix = np.array([
            [0.0, 10.0, 50.0],
            [10.0, 0.0, 50.0],
            [50.0, 50.0, 0.0],
        ])

        solution = VRPSolver(
            orders=orders,
            fleet=fleet,
            depot=sample_depot,
            distance_matrix=dist_matrix,
            duration_matrix=dur_matrix,
            config={
                "constraints": {"enforce_city_limit": False},
                "routing": {
                    "priority_time_tolerance": 0,
                    "non_priority_time_tolerance": 0,
                },
            },
        ).solve(optimization_strategy="balanced", time_limit=10)

        assert solution.total_orders_delivered == 1
        assert len(solution.unassigned_orders) == 1
