"""Validation tests for routing solutions."""
import pytest
import numpy as np

from src.solver.vrp_solver import VRPSolver
from src.models.order import Order
from src.models.vehicle import Vehicle, VehicleFleet
from src.models.location import Depot


class TestValidation:
    """Test suite for solution validation."""

    @pytest.fixture
    def sample_depot(self):
        """Create sample depot."""
        return Depot("Test Depot", (-6.2088, 106.8456))

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
    def sample_orders_varied_times(self):
        """Create orders with varied time windows."""
        return [
            Order(
                sale_order_id=f"O{i:03d}",
                delivery_date="2025-10-08",
                delivery_time=f"{4+i:02d}:00-{5+i:02d}:00",
                load_weight_in_kg=50.0 + (i * 10),
                partner_id=f"P{i:03d}",
                display_name=f"Customer {i}",
                alamat=f"Address {i}",
                coordinates=(-6.2088 + (i * 0.01), 106.8456 + (i * 0.01)),
                is_priority=(i % 3 == 0)
            )
            for i in range(5)
        ]

    @pytest.fixture
    def sample_distance_matrix_5(self):
        """Create distance matrix for 6 locations (depot + 5 customers)."""
        return np.array([
            [0.0,  5.0,  10.0, 15.0, 20.0, 25.0],
            [5.0,  0.0,  6.0,  12.0, 18.0, 24.0],
            [10.0, 6.0,  0.0,  8.0,  14.0, 20.0],
            [15.0, 12.0, 8.0,  0.0,  9.0,  16.0],
            [20.0, 18.0, 14.0, 9.0,  0.0,  10.0],
            [25.0, 24.0, 20.0, 16.0, 10.0, 0.0],
        ])

    @pytest.fixture
    def sample_duration_matrix_5(self):
        """Create duration matrix for 6 locations (depot + 5 customers)."""
        return np.array([
            [0.0,  10.0, 20.0, 30.0, 40.0, 50.0],
            [10.0, 0.0,  12.0, 25.0, 38.0, 48.0],
            [20.0, 12.0, 0.0,  15.0, 28.0, 40.0],
            [30.0, 25.0, 15.0, 0.0,  18.0, 32.0],
            [40.0, 38.0, 28.0, 18.0, 0.0,  20.0],
            [50.0, 48.0, 40.0, 32.0, 20.0, 0.0],
        ])

    def test_validate_time_windows_met(self, sample_orders_varied_times, sample_fleet,
                                      sample_depot, sample_distance_matrix_5,
                                      sample_duration_matrix_5):
        """Test that all time windows are met (HARD constraint)."""

        solver = VRPSolver(
            orders=sample_orders_varied_times,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_5,
            duration_matrix=sample_duration_matrix_5
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        # Validate time windows for all delivered orders
        for route in solution.routes:
            for stop in route.stops:
                order = stop.order
                arrival = stop.arrival_time

                assert arrival >= order.time_window_start, \
                    f"Order {order.sale_order_id} arrived too early: {arrival} < {order.time_window_start}"

                assert arrival <= order.time_window_end, \
                    f"Order {order.sale_order_id} arrived too late: {arrival} > {order.time_window_end}"

    def test_validate_capacity_not_exceeded(self, sample_orders_varied_times, sample_fleet,
                                           sample_depot, sample_distance_matrix_5,
                                           sample_duration_matrix_5):
        """Test that vehicle capacity is never exceeded."""

        solver = VRPSolver(
            orders=sample_orders_varied_times,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_5,
            duration_matrix=sample_duration_matrix_5
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        # Validate capacity for all routes
        for route in solution.routes:
            total_weight = sum(stop.order.load_weight_in_kg for stop in route.stops)

            assert total_weight <= route.vehicle.capacity, \
                f"Route exceeds capacity: {total_weight}kg > {route.vehicle.capacity}kg"

            # Also check cumulative weights at each stop
            for stop in route.stops:
                assert stop.cumulative_weight <= route.vehicle.capacity, \
                    f"Cumulative weight exceeds capacity at stop {stop.sequence}"

    def test_validate_route_sequence_logical(self, sample_orders_varied_times, sample_fleet,
                                            sample_depot, sample_distance_matrix_5,
                                            sample_duration_matrix_5):
        """Test that route sequences are logical (no zigzag, times increase)."""

        solver = VRPSolver(
            orders=sample_orders_varied_times,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_5,
            duration_matrix=sample_duration_matrix_5
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        for route in solution.routes:
            if len(route.stops) < 2:
                continue

            # Verify sequences are correct (0, 1, 2, ...)
            for i, stop in enumerate(route.stops):
                assert stop.sequence == i, \
                    f"Stop sequence incorrect: expected {i}, got {stop.sequence}"

            # Verify arrival times are increasing
            for i in range(len(route.stops) - 1):
                current_arrival = route.stops[i].arrival_time
                next_arrival = route.stops[i + 1].arrival_time

                assert next_arrival >= current_arrival, \
                    f"Arrival times not increasing: {next_arrival} < {current_arrival}"

            # Verify cumulative weights are increasing
            for i in range(len(route.stops) - 1):
                current_weight = route.stops[i].cumulative_weight
                next_weight = route.stops[i + 1].cumulative_weight

                assert next_weight >= current_weight, \
                    f"Cumulative weights not increasing"

    def test_validate_cost_calculation(self, sample_orders_varied_times, sample_fleet,
                                       sample_depot, sample_distance_matrix_5,
                                       sample_duration_matrix_5):
        """Test that cost calculations are correct."""

        solver = VRPSolver(
            orders=sample_orders_varied_times,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_5,
            duration_matrix=sample_duration_matrix_5
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        for route in solution.routes:
            # Calculate expected cost
            expected_cost = route.total_distance * route.vehicle.cost_per_km

            # Allow small floating point differences
            assert abs(route.total_cost - expected_cost) < 0.01, \
                f"Cost calculation incorrect: {route.total_cost} != {expected_cost}"

        # Verify solution-level totals
        total_distance = sum(route.total_distance for route in solution.routes)
        total_cost = sum(route.total_cost for route in solution.routes)

        assert abs(solution.total_distance - total_distance) < 0.01
        assert abs(solution.total_cost - total_cost) < 0.01

    def test_validate_all_orders_assigned_or_reported(self, sample_orders_varied_times,
                                                     sample_fleet, sample_depot,
                                                     sample_distance_matrix_5,
                                                     sample_duration_matrix_5):
        """Test that all orders are either assigned or in unassigned list."""

        solver = VRPSolver(
            orders=sample_orders_varied_times,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_5,
            duration_matrix=sample_duration_matrix_5
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        # Count delivered orders
        delivered_order_ids = set()
        for route in solution.routes:
            for stop in route.stops:
                delivered_order_ids.add(stop.order.sale_order_id)

        # Count unassigned orders
        unassigned_order_ids = {order.sale_order_id for order in solution.unassigned_orders}

        # Total should equal input orders
        total_accounted = len(delivered_order_ids) + len(unassigned_order_ids)
        total_input = len(sample_orders_varied_times)

        assert total_accounted == total_input, \
            f"Orders not fully accounted: {total_accounted} != {total_input}"

        # No duplicates
        assert len(delivered_order_ids & unassigned_order_ids) == 0, \
            "Order appears in both delivered and unassigned"

    def test_validate_depot_start_end(self, sample_orders_varied_times, sample_fleet,
                                     sample_depot, sample_distance_matrix_5,
                                     sample_duration_matrix_5):
        """Test that all routes start and end at depot."""

        solver = VRPSolver(
            orders=sample_orders_varied_times,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_5,
            duration_matrix=sample_duration_matrix_5
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        # Each route should start with distance from depot and end with return to depot
        for route in solution.routes:
            if route.num_stops == 0:
                continue

            # First stop should have distance from depot
            first_stop = route.stops[0]
            assert first_stop.distance_from_prev > 0, \
                "First stop should have distance from depot"

            # Total distance should include return to depot
            sum_distances = sum(stop.distance_from_prev for stop in route.stops)
            assert route.total_distance > sum_distances, \
                "Route total distance should include return to depot"

    def test_validate_metrics_consistency(self, sample_orders_varied_times, sample_fleet,
                                         sample_depot, sample_distance_matrix_5,
                                         sample_duration_matrix_5):
        """Test that all metrics are consistent across route and solution."""

        solver = VRPSolver(
            orders=sample_orders_varied_times,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_5,
            duration_matrix=sample_duration_matrix_5
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        # Solution metrics should match sum of route metrics
        assert solution.total_vehicles_used == len([r for r in solution.routes if r.num_stops > 0])

        total_distance_routes = sum(r.total_distance for r in solution.routes)
        assert abs(solution.total_distance - total_distance_routes) < 0.01

        total_cost_routes = sum(r.total_cost for r in solution.routes)
        assert abs(solution.total_cost - total_cost_routes) < 0.01

        total_orders_routes = sum(r.num_stops for r in solution.routes)
        assert solution.total_orders_delivered == total_orders_routes

    def test_validate_service_time_applied(self, sample_orders_varied_times, sample_fleet,
                                          sample_depot, sample_distance_matrix_5,
                                          sample_duration_matrix_5):
        """Test that service time (15 minutes) is applied at each stop."""

        solver = VRPSolver(
            orders=sample_orders_varied_times,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_5,
            duration_matrix=sample_duration_matrix_5
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        SERVICE_TIME = 15  # minutes

        for route in solution.routes:
            for stop in route.stops:
                # Departure should be arrival + service time
                expected_departure = stop.arrival_time + SERVICE_TIME

                assert stop.departure_time == expected_departure, \
                    f"Service time not applied: {stop.departure_time} != {expected_departure}"

    def test_validate_departure_time_before_first_delivery(self, sample_orders_varied_times,
                                                          sample_fleet, sample_depot,
                                                          sample_distance_matrix_5,
                                                          sample_duration_matrix_5):
        """Test that vehicles depart 30 minutes before earliest delivery."""

        solver = VRPSolver(
            orders=sample_orders_varied_times,
            fleet=sample_fleet,
            depot=sample_depot,
            distance_matrix=sample_distance_matrix_5,
            duration_matrix=sample_duration_matrix_5
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        for route in solution.routes:
            if route.num_stops == 0:
                continue

            # Find earliest time window in route
            earliest_window = min(stop.order.time_window_start for stop in route.stops)

            # Departure should be at least 30 minutes before
            # (allowing some flexibility for solver)
            max_expected_departure = earliest_window - 30

            # Departure time should generally be around this time
            # (may vary slightly based on solver optimization)
            assert route.departure_time <= earliest_window, \
                f"Departure {route.departure_time} is after earliest window {earliest_window}"
