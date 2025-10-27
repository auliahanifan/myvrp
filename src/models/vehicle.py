"""
Vehicle model for VRP solver.
Represents a delivery vehicle with capacity and cost information.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class Vehicle:
    """
    Represents a delivery vehicle.

    Attributes:
        name: Vehicle type name (e.g., "Blind Van", "Mobil")
        capacity: Maximum load capacity in kilograms
        cost_per_km: Cost per kilometer for this vehicle type
        vehicle_id: Optional unique identifier for the vehicle instance
        fixed_cost: Fixed cost per vehicle usage (for minimize vehicle strategy)
    """
    name: str
    capacity: float  # in kg
    cost_per_km: float  # in Rupiah
    vehicle_id: Optional[int] = None
    fixed_cost: float = 0.0  # Fixed cost for using this vehicle

    def __post_init__(self):
        """Validate vehicle data after initialization."""
        if self.capacity <= 0:
            raise ValueError(f"Vehicle {self.name}: Capacity must be positive")

        if self.cost_per_km < 0:
            raise ValueError(f"Vehicle {self.name}: Cost per km must be non-negative")

    def clone_with_id(self, vehicle_id: int) -> "Vehicle":
        """
        Create a clone of this vehicle with a specific ID.
        Used for creating multiple instances of the same vehicle type.

        Args:
            vehicle_id: Unique identifier for this vehicle instance

        Returns:
            New Vehicle instance with the same specs but different ID
        """
        return Vehicle(
            name=f"{self.name}_{vehicle_id}",
            capacity=self.capacity,
            cost_per_km=self.cost_per_km,
            vehicle_id=vehicle_id,
            fixed_cost=self.fixed_cost,
        )

    def __repr__(self) -> str:
        """String representation of the vehicle."""
        return (
            f"Vehicle({self.name}, capacity={self.capacity}kg, "
            f"cost={self.cost_per_km}/km)"
        )


@dataclass
class VehicleFleet:
    """
    Represents a fleet of vehicles available for routing.

    Attributes:
        vehicle_types: List of vehicle types with their counts
        return_to_depot: If True, all vehicles must return to depot
        priority_time_tolerance: Time tolerance for priority orders (minutes)
        non_priority_time_tolerance: Time tolerance for non-priority orders (minutes)
        multiple_trips: If True, vehicles can make multiple trips
    """
    vehicle_types: list[tuple[Vehicle, int, bool]]  # (vehicle, count, unlimited)
    return_to_depot: bool = True
    priority_time_tolerance: int = 0
    non_priority_time_tolerance: int = 20
    multiple_trips: bool = True
    relax_time_windows: bool = False
    time_window_relaxation_minutes: int = 0

    def __post_init__(self):
        """Validate fleet data."""
        if not self.vehicle_types:
            raise ValueError("Fleet must have at least one vehicle type")

    def get_all_vehicles(self) -> list[Vehicle]:
        """
        Get all vehicle instances based on configuration.
        Ordered by priority (highest cost first to minimize vehicle count).

        Returns:
            List of Vehicle instances
        """
        vehicles = []
        vehicle_id = 0

        for vehicle_type, count, unlimited in self.vehicle_types:
            for i in range(count):
                vehicles.append(vehicle_type.clone_with_id(vehicle_id))
                vehicle_id += 1

        return vehicles

    def get_vehicle_by_index(self, index: int) -> Vehicle:
        """
        Get a vehicle instance by index.
        Handles both fixed and unlimited vehicle types.

        Args:
            index: Vehicle index

        Returns:
            Vehicle instance
        """
        all_vehicles = self.get_all_vehicles()

        if index < len(all_vehicles):
            return all_vehicles[index]

        # If beyond fixed vehicles, check for unlimited types
        for vehicle_type, count, unlimited in self.vehicle_types:
            if unlimited:
                # Clone the unlimited vehicle type
                return vehicle_type.clone_with_id(index)

        raise ValueError(f"Vehicle index {index} out of range and no unlimited vehicles available")

    def get_max_vehicles(self) -> int:
        """
        Get maximum number of fixed vehicles available.

        Returns:
            Total count of fixed vehicles
        """
        return sum(count for _, count, _ in self.vehicle_types)

    def has_unlimited(self) -> bool:
        """
        Check if fleet has any unlimited vehicle types.

        Returns:
            True if any vehicle type is unlimited
        """
        return any(unlimited for _, _, unlimited in self.vehicle_types)

    def __len__(self) -> int:
        """Return the total number of fixed vehicles."""
        return self.get_max_vehicles()

    def __repr__(self) -> str:
        """String representation of the fleet."""
        fixed_count = self.get_max_vehicles()
        unlimited_str = " + unlimited" if self.has_unlimited() else ""
        return f"VehicleFleet({fixed_count} vehicles{unlimited_str}, {len(self.vehicle_types)} types)"
