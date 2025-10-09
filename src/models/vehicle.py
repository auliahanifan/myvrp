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
        name: Vehicle type name (e.g., "L300", "Granmax")
        capacity: Maximum load capacity in kilograms
        cost_per_km: Cost per kilometer for this vehicle type
        vehicle_id: Optional unique identifier for the vehicle instance
    """
    name: str
    capacity: float  # in kg
    cost_per_km: float  # in Rupiah
    vehicle_id: Optional[int] = None

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
        vehicle_types: List of vehicle types available
        unlimited: If True, unlimited vehicles of each type are available
    """
    vehicle_types: list[Vehicle]
    unlimited: bool = True

    def __post_init__(self):
        """Validate fleet data."""
        if not self.vehicle_types:
            raise ValueError("Fleet must have at least one vehicle type")

    def get_vehicle_by_index(self, index: int) -> Vehicle:
        """
        Get a vehicle instance by index.
        If unlimited fleet, cycles through vehicle types.

        Args:
            index: Vehicle index

        Returns:
            Vehicle instance
        """
        if not self.unlimited and index >= len(self.vehicle_types):
            raise ValueError(f"Vehicle index {index} out of range for limited fleet")

        # Cycle through vehicle types for unlimited fleet
        type_index = index % len(self.vehicle_types)
        base_vehicle = self.vehicle_types[type_index]
        return base_vehicle.clone_with_id(index)

    def __len__(self) -> int:
        """Return the number of vehicle types in the fleet."""
        return len(self.vehicle_types)

    def __repr__(self) -> str:
        """String representation of the fleet."""
        fleet_type = "Unlimited" if self.unlimited else "Limited"
        return f"VehicleFleet({fleet_type}, {len(self.vehicle_types)} types)"
