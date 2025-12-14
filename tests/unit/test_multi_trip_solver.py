"""Unit tests for multi-trip solver module."""
import pytest
import numpy as np
from src.solver.multi_trip_solver import MultiTripSolver, PhysicalVehicleAssignment
from src.models.order import Order
from src.models.vehicle import Vehicle, VehicleFleet
from src.models.location import Depot
from src.models.route import Route, RouteStop


class TestPhysicalVehicleAssignment:
    """Test suite for PhysicalVehicleAssignment dataclass."""

    def test_trip_count(self):
        """Test trip count property."""
        vehicle = Vehicle(name="Motor", capacity=80, cost_per_km=1500)
        route1 = Route(vehicle=vehicle, trip_number=1)
        route2 = Route(vehicle=vehicle, trip_number=2)

        assignment = PhysicalVehicleAssignment(
            physical_id="Motor_1",
            vehicle_type="Motor",
            source="DEPOT",
            trips=[route1, route2],
            last_end_time=480,
        )

        assert assignment.trip_count == 2


class TestMultiTripSolver:
    """Test suite for MultiTripSolver class."""

    @pytest.fixture
    def sample_depot(self):
        """Create sample depot."""
        return Depot("Test Depot", (-6.2088, 106.8456))

    @pytest.fixture
    def sample_orders_two_clusters(self):
        """Create orders that should form two time window clusters."""
        return [
            # Cluster 1: Morning (07:00-08:30)
            Order(
                sale_order_id="O001",
                delivery_date="2025-10-08",
                delivery_time="07:00-08:00",
                load_weight_in_kg=50.0,
                partner_id="P001",
                display_name="Customer 1",
                alamat="Address 1",
                coordinates=(-6.2100, 106.8500),
                is_priority=False,
            ),
            Order(
                sale_order_id="O002",
                delivery_date="2025-10-08",
                delivery_time="07:30-08:30",
                load_weight_in_kg=30.0,
                partner_id="P002",
                display_name="Customer 2",
                alamat="Address 2",
                coordinates=(-6.2200, 106.8600),
                is_priority=False,
            ),
            # Cluster 2: Late morning (10:00-11:30)
            Order(
                sale_order_id="O003",
                delivery_date="2025-10-08",
                delivery_time="10:00-11:00",
                load_weight_in_kg=40.0,
                partner_id="P003",
                display_name="Customer 3",
                alamat="Address 3",
                coordinates=(-6.2300, 106.8700),
                is_priority=False,
            ),
            Order(
                sale_order_id="O004",
                delivery_date="2025-10-08",
                delivery_time="10:30-11:30",
                load_weight_in_kg=25.0,
                partner_id="P004",
                display_name="Customer 4",
                alamat="Address 4",
                coordinates=(-6.2400, 106.8800),
                is_priority=False,
            ),
        ]

    @pytest.fixture
    def sample_orders_single_cluster(self):
        """Create orders that should form a single cluster."""
        return [
            Order(
                sale_order_id="O001",
                delivery_date="2025-10-08",
                delivery_time="07:00-08:00",
                load_weight_in_kg=50.0,
                partner_id="P001",
                display_name="Customer 1",
                alamat="Address 1",
                coordinates=(-6.2100, 106.8500),
                is_priority=False,
            ),
            Order(
                sale_order_id="O002",
                delivery_date="2025-10-08",
                delivery_time="07:30-08:30",
                load_weight_in_kg=30.0,
                partner_id="P002",
                display_name="Customer 2",
                alamat="Address 2",
                coordinates=(-6.2200, 106.8600),
                is_priority=False,
            ),
        ]

    @pytest.fixture
    def sample_fleet(self):
        """Create sample vehicle fleet with multiple_trips enabled."""
        motor = Vehicle(name="Sepeda Motor", capacity=80, cost_per_km=1500)
        return VehicleFleet(
            vehicle_types=[(motor, 10, False)],
            multiple_trips=True,
        )

    @pytest.fixture
    def sample_distance_matrix_5x5(self):
        """Create 5x5 distance matrix (depot + 4 customers)."""
        return np.array(
            [
                [0.0, 5.0, 10.0, 8.0, 12.0],  # Depot
                [5.0, 0.0, 6.0, 4.0, 8.0],  # Customer 1
                [10.0, 6.0, 0.0, 7.0, 5.0],  # Customer 2
                [8.0, 4.0, 7.0, 0.0, 6.0],  # Customer 3
                [12.0, 8.0, 5.0, 6.0, 0.0],  # Customer 4
            ]
        )

    @pytest.fixture
    def sample_duration_matrix_5x5(self):
        """Create 5x5 duration matrix (depot + 4 customers)."""
        return np.array(
            [
                [0.0, 15.0, 25.0, 20.0, 30.0],  # Depot
                [15.0, 0.0, 18.0, 12.0, 24.0],  # Customer 1
                [25.0, 18.0, 0.0, 21.0, 15.0],  # Customer 2
                [20.0, 12.0, 21.0, 0.0, 18.0],  # Customer 3
                [30.0, 24.0, 15.0, 18.0, 0.0],  # Customer 4
            ]
        )

    @pytest.fixture
    def sample_distance_matrix_3x3(self):
        """Create 3x3 distance matrix (depot + 2 customers)."""
        return np.array(
            [
                [0.0, 5.0, 10.0],  # Depot
                [5.0, 0.0, 6.0],  # Customer 1
                [10.0, 6.0, 0.0],  # Customer 2
            ]
        )

    @pytest.fixture
    def sample_duration_matrix_3x3(self):
        """Create 3x3 duration matrix (depot + 2 customers)."""
        return np.array(
            [
                [0.0, 15.0, 25.0],  # Depot
                [15.0, 0.0, 18.0],  # Customer 1
                [25.0, 18.0, 0.0],  # Customer 2
            ]
        )

    @pytest.fixture
    def multi_trip_config(self):
        """Create multi-trip enabled config."""
        return {
            "routing": {
                "multi_trip": {
                    "enabled": True,
                    "buffer_minutes": 60,
                    "clustering": {
                        "gap_threshold_minutes": 60,
                        "min_cluster_size": 1,
                    },
                    "vehicle_reuse": {
                        "same_source_only": True,
                        "max_trips_per_vehicle": 3,
                    },
                }
            }
        }

    @pytest.fixture
    def multi_trip_disabled_config(self):
        """Create multi-trip disabled config."""
        return {"routing": {"multi_trip": {"enabled": False}}}

    def test_solver_initialization(
        self,
        sample_depot,
        sample_orders_two_clusters,
        sample_fleet,
        sample_distance_matrix_5x5,
        sample_duration_matrix_5x5,
        multi_trip_config,
    ):
        """Test solver initialization with multi-trip config."""
        solver = MultiTripSolver(
            orders=sample_orders_two_clusters,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_5x5,
            duration_matrix=sample_duration_matrix_5x5,
            config=multi_trip_config,
        )

        assert solver.enabled is True
        assert solver.buffer_minutes == 60
        assert solver.max_trips == 3
        assert solver.gap_threshold == 60

    def test_solver_disabled(
        self,
        sample_depot,
        sample_orders_single_cluster,
        sample_fleet,
        sample_distance_matrix_3x3,
        sample_duration_matrix_3x3,
        multi_trip_disabled_config,
    ):
        """Test solver falls back to single solve when disabled."""
        solver = MultiTripSolver(
            orders=sample_orders_single_cluster,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_3x3,
            duration_matrix=sample_duration_matrix_3x3,
            config=multi_trip_disabled_config,
        )

        assert solver.enabled is False

        solution = solver.solve(time_limit=30, source="DEPOT")

        # Should complete without error
        assert solution is not None

    def test_solve_empty_orders(
        self,
        sample_depot,
        sample_fleet,
        multi_trip_config,
    ):
        """Test solve with empty orders."""
        empty_matrix = np.array([[0.0]])

        solver = MultiTripSolver(
            orders=[],
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=empty_matrix,
            duration_matrix=empty_matrix,
            config=multi_trip_config,
        )

        solution = solver.solve(time_limit=30, source="DEPOT")

        assert solution is not None
        assert len(solution.routes) == 0
        assert len(solution.unassigned_orders) == 0

    def test_solve_single_cluster_fallback(
        self,
        sample_depot,
        sample_orders_single_cluster,
        sample_fleet,
        sample_distance_matrix_3x3,
        sample_duration_matrix_3x3,
        multi_trip_config,
    ):
        """Test solver falls back to single solve with one cluster."""
        solver = MultiTripSolver(
            orders=sample_orders_single_cluster,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_3x3,
            duration_matrix=sample_duration_matrix_3x3,
            config=multi_trip_config,
        )

        solution = solver.solve(time_limit=30, source="DEPOT")

        # Single cluster should use fallback single solve
        assert solution is not None
        # All orders should be delivered or in routes
        total_delivered = sum(r.num_stops for r in solution.routes)
        total_unassigned = len(solution.unassigned_orders)
        assert total_delivered + total_unassigned == 2

    def test_get_vehicle_type(
        self,
        sample_depot,
        sample_orders_single_cluster,
        sample_fleet,
        sample_distance_matrix_3x3,
        sample_duration_matrix_3x3,
        multi_trip_config,
    ):
        """Test vehicle type extraction from vehicle name."""
        solver = MultiTripSolver(
            orders=sample_orders_single_cluster,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_3x3,
            duration_matrix=sample_duration_matrix_3x3,
            config=multi_trip_config,
        )

        # Test with ID suffix
        assert solver._get_vehicle_type("Sepeda Motor_1") == "Sepeda Motor"
        assert solver._get_vehicle_type("Motor_123") == "Motor"

        # Test without ID suffix
        assert solver._get_vehicle_type("Motor") == "Motor"
        assert solver._get_vehicle_type("Sepeda Motor") == "Sepeda Motor"

    def test_extract_submatrix(
        self,
        sample_depot,
        sample_orders_single_cluster,
        sample_fleet,
        sample_distance_matrix_5x5,
        sample_duration_matrix_5x5,
        multi_trip_config,
    ):
        """Test submatrix extraction."""
        solver = MultiTripSolver(
            orders=sample_orders_single_cluster,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_5x5,
            duration_matrix=sample_duration_matrix_5x5,
            config=multi_trip_config,
        )

        # Extract submatrix for depot (0) and customers 1, 3
        indices = [0, 1, 3]
        submatrix = solver._extract_submatrix(sample_distance_matrix_5x5, indices)

        assert submatrix.shape == (3, 3)
        assert submatrix[0, 0] == 0.0  # depot to depot
        assert submatrix[0, 1] == 5.0  # depot to customer 1
        assert submatrix[0, 2] == 8.0  # depot to customer 3
        assert submatrix[1, 2] == 4.0  # customer 1 to customer 3


class TestMultiTripIntegration:
    """Integration tests for multi-trip solving."""

    @pytest.fixture
    def depot(self):
        return Depot("Test Depot", (-6.2088, 106.8456))

    @pytest.fixture
    def fleet_with_limited_vehicles(self):
        """Fleet with limited vehicles to test multi-trip assignment."""
        motor = Vehicle(name="Sepeda Motor", capacity=80, cost_per_km=1500)
        return VehicleFleet(
            vehicle_types=[(motor, 2, False)],  # Only 2 motors
            multiple_trips=True,
        )

    @pytest.fixture
    def orders_requiring_multi_trip(self):
        """Create orders that would require multi-trip if vehicles are limited."""
        orders = []
        # Morning orders (07:00-09:00)
        for i in range(3):
            orders.append(
                Order(
                    sale_order_id=f"M{i+1}",
                    delivery_date="2025-10-08",
                    delivery_time=f"07:{i*20:02d}-08:{i*20:02d}",
                    load_weight_in_kg=30.0,
                    partner_id=f"PM{i+1}",
                    display_name=f"Morning Customer {i+1}",
                    alamat=f"Address M{i+1}",
                    coordinates=(-6.21 + i * 0.01, 106.85 + i * 0.01),
                    is_priority=False,
                )
            )

        # Afternoon orders (12:00-14:00)
        for i in range(3):
            orders.append(
                Order(
                    sale_order_id=f"A{i+1}",
                    delivery_date="2025-10-08",
                    delivery_time=f"12:{i*20:02d}-13:{i*20:02d}",
                    load_weight_in_kg=30.0,
                    partner_id=f"PA{i+1}",
                    display_name=f"Afternoon Customer {i+1}",
                    alamat=f"Address A{i+1}",
                    coordinates=(-6.24 + i * 0.01, 106.88 + i * 0.01),
                    is_priority=False,
                )
            )

        return orders

    @pytest.fixture
    def large_distance_matrix(self):
        """7x7 matrix for depot + 6 orders."""
        n = 7
        matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                if i != j:
                    matrix[i, j] = abs(i - j) * 3.0 + 2.0
        return matrix

    @pytest.fixture
    def large_duration_matrix(self):
        """7x7 duration matrix for depot + 6 orders."""
        n = 7
        matrix = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                if i != j:
                    matrix[i, j] = abs(i - j) * 10.0 + 5.0
        return matrix

    def test_multi_trip_solution_structure(
        self,
        depot,
        fleet_with_limited_vehicles,
        orders_requiring_multi_trip,
        large_distance_matrix,
        large_duration_matrix,
    ):
        """Test that multi-trip solver produces valid solution structure."""
        config = {
            "routing": {
                "multi_trip": {
                    "enabled": True,
                    "buffer_minutes": 60,
                    "clustering": {
                        "gap_threshold_minutes": 90,
                        "min_cluster_size": 1,
                    },
                    "vehicle_reuse": {
                        "same_source_only": True,
                        "max_trips_per_vehicle": 3,
                    },
                }
            }
        }

        solver = MultiTripSolver(
            orders=orders_requiring_multi_trip,
            fleet=fleet_with_limited_vehicles,
            depot=depot,
            distance_matrix=large_distance_matrix,
            duration_matrix=large_duration_matrix,
            config=config,
        )

        solution = solver.solve(time_limit=60, source="DEPOT")

        assert solution is not None
        assert solution.routes is not None

        # Check that routes have valid trip numbers
        for route in solution.routes:
            assert route.trip_number >= 1
            assert route.source == "DEPOT"

        # Check total orders accounted for
        delivered = sum(r.num_stops for r in solution.routes)
        unassigned = len(solution.unassigned_orders)
        assert delivered + unassigned == 6
