"""
Route model for VRP solver.
Represents a delivery route for a vehicle with ordered stops.
"""
from dataclasses import dataclass, field
from datetime import time
from typing import List, Optional
from .order import Order
from .vehicle import Vehicle


@dataclass
class RouteStop:
    """
    Represents a single stop in a route.

    Attributes:
        order: The order to deliver at this stop
        arrival_time: Time of arrival at this stop (minutes from midnight)
        departure_time: Time of departure from this stop (minutes from midnight)
        distance_from_prev: Distance from previous stop in kilometers
        cumulative_weight: Cumulative weight carried up to this stop
        sequence: Stop sequence number (0 = depot, 1+ = customer stops)
    """
    order: Order
    arrival_time: int  # minutes from midnight
    departure_time: int  # minutes from midnight
    distance_from_prev: float  # km
    cumulative_weight: float  # kg
    sequence: int

    def format_time(self, minutes: int) -> str:
        """
        Format time in minutes from midnight to HH:MM string.

        Args:
            minutes: Time in minutes from midnight

        Returns:
            Time string in HH:MM format
        """
        hours = minutes // 60
        mins = minutes % 60
        return f"{hours:02d}:{mins:02d}"

    @property
    def arrival_time_str(self) -> str:
        """Get arrival time as HH:MM string."""
        return self.format_time(self.arrival_time)

    @property
    def departure_time_str(self) -> str:
        """Get departure time as HH:MM string."""
        return self.format_time(self.departure_time)

    def __repr__(self) -> str:
        """String representation of the stop."""
        return (
            f"Stop({self.sequence}: {self.order.display_name}, "
            f"arrive={self.arrival_time_str}, weight={self.cumulative_weight}kg)"
        )


@dataclass
class Route:
    """
    Represents a complete delivery route for one vehicle.

    Attributes:
        vehicle: The vehicle assigned to this route
        stops: List of stops in order (excluding depot)
        total_distance: Total distance traveled in kilometers
        total_cost: Total cost of the route in Rupiah
        departure_time: Departure time from depot (minutes from midnight)
    """
    vehicle: Vehicle
    stops: List[RouteStop] = field(default_factory=list)
    total_distance: float = 0.0
    total_cost: float = 0.0
    departure_time: int = 0  # minutes from midnight

    @property
    def total_weight(self) -> float:
        """Calculate total weight delivered on this route."""
        return sum(stop.order.load_weight_in_kg for stop in self.stops)

    @property
    def num_stops(self) -> int:
        """Get number of customer stops (excluding depot)."""
        return len(self.stops)

    @property
    def departure_time_str(self) -> str:
        """Get departure time as HH:MM string."""
        hours = self.departure_time // 60
        mins = self.departure_time % 60
        return f"{hours:02d}:{mins:02d}"

    def add_stop(self, stop: RouteStop):
        """
        Add a stop to the route.

        Args:
            stop: RouteStop to add
        """
        self.stops.append(stop)

    def calculate_metrics(self):
        """Calculate total distance and cost for the route."""
        self.total_distance = sum(stop.distance_from_prev for stop in self.stops)
        # Add return distance to depot (will be set by solver)
        self.total_cost = self.total_distance * self.vehicle.cost_per_km

    def validate(self) -> List[str]:
        """
        Validate route constraints.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Check capacity constraint
        if self.total_weight > self.vehicle.capacity:
            errors.append(
                f"Route exceeds vehicle capacity: {self.total_weight}kg > "
                f"{self.vehicle.capacity}kg"
            )

        # Check time window constraints for each stop
        for stop in self.stops:
            if stop.arrival_time < stop.order.time_window_start:
                errors.append(
                    f"Stop {stop.sequence} ({stop.order.display_name}): "
                    f"Arrived too early at {stop.arrival_time_str}, "
                    f"window starts at {stop.order.delivery_time}"
                )
            if stop.arrival_time > stop.order.time_window_end:
                errors.append(
                    f"Stop {stop.sequence} ({stop.order.display_name}): "
                    f"Arrived too late at {stop.arrival_time_str}, "
                    f"window ends at {stop.order.delivery_time}"
                )

        return errors

    def __repr__(self) -> str:
        """String representation of the route."""
        return (
            f"Route({self.vehicle.name}, {self.num_stops} stops, "
            f"{self.total_distance:.1f}km, Rp{self.total_cost:,.0f})"
        )


@dataclass
class RoutingSolution:
    """
    Represents the complete solution for the VRP.

    Attributes:
        routes: List of routes (one per vehicle)
        unassigned_orders: List of orders that couldn't be assigned
        optimization_strategy: Strategy used ("minimize_vehicles", "minimize_cost", "balanced")
        computation_time: Time taken to compute solution in seconds
    """
    routes: List[Route]
    unassigned_orders: List[Order] = field(default_factory=list)
    optimization_strategy: str = "balanced"
    computation_time: float = 0.0

    @property
    def total_vehicles_used(self) -> int:
        """Get total number of vehicles used."""
        return len([r for r in self.routes if r.num_stops > 0])

    @property
    def total_distance(self) -> float:
        """Get total distance across all routes."""
        return sum(route.total_distance for route in self.routes)

    @property
    def total_cost(self) -> float:
        """Get total cost across all routes."""
        return sum(route.total_cost for route in self.routes)

    @property
    def total_orders_delivered(self) -> int:
        """Get total number of orders delivered."""
        return sum(route.num_stops for route in self.routes)

    def validate(self) -> List[str]:
        """
        Validate all routes in the solution.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        for i, route in enumerate(self.routes):
            route_errors = route.validate()
            if route_errors:
                errors.extend([f"Route {i}: {err}" for err in route_errors])

        if self.unassigned_orders:
            errors.append(
                f"{len(self.unassigned_orders)} orders could not be assigned"
            )

        return errors

    def __repr__(self) -> str:
        """String representation of the solution."""
        return (
            f"RoutingSolution({self.total_vehicles_used} vehicles, "
            f"{self.total_orders_delivered} orders, "
            f"{self.total_distance:.1f}km, Rp{self.total_cost:,.0f})"
        )
