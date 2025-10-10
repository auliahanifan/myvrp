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
        # Create orders that exceed single vehicle capacity (300kg max for smallest)
        heavy_orders = [
            Order(
                sale_order_id="H001",
                delivery_date="2025-10-08",
                delivery_time="04:00-08:00",
                load_weight_in_kg=250.0,
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
                load_weight_in_kg=250.0,
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
                load_weight_in_kg=250.0,
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

        # Should use multiple vehicles since each order is 250kg (can't fit 2 in 500kg vehicle)
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
