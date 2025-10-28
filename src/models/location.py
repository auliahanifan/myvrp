"""
Location model for VRP solver.
Represents geographic locations (depot and customer locations).
"""
from dataclasses import dataclass
from typing import Tuple


@dataclass
class Location:
    """
    Represents a geographic location.

    Attributes:
        name: Location name or identifier
        coordinates: Tuple of (latitude, longitude)
        address: Full address (optional)
    """
    name: str
    coordinates: Tuple[float, float]  # (latitude, longitude)
    address: str = ""

    def __post_init__(self):
        """Validate location data."""
        lat, lng = self.coordinates
        if not (-90 <= lat <= 90):
            raise ValueError(f"Location {self.name}: Invalid latitude {lat}")
        if not (-180 <= lng <= 180):
            raise ValueError(f"Location {self.name}: Invalid longitude {lng}")

    @property
    def latitude(self) -> float:
        """Get latitude."""
        return self.coordinates[0]

    @property
    def longitude(self) -> float:
        """Get longitude."""
        return self.coordinates[1]

    def to_tuple(self) -> Tuple[float, float]:
        """Get coordinates as tuple."""
        return self.coordinates

    def __repr__(self) -> str:
        """String representation of the location."""
        return f"Location({self.name}, {self.coordinates})"


@dataclass
class Depot(Location):
    """
    Represents the depot (warehouse/distribution center).
    All routes start and end at the depot.
    """

    def __post_init__(self):
        """Validate depot data."""
        super().__post_init__()
        if not self.name:
            self.name = "Depot"

    def __repr__(self) -> str:
        """String representation of the depot."""
        return f"Depot({self.name}, {self.coordinates})"


@dataclass
class Hub(Location):
    """
    Represents a hub for two-tier delivery routing.
    Used for consolidation: Blind Van (DEPOT -> HUB), then Sepeda Motor (HUB -> Customer).
    """

    def __post_init__(self):
        """Validate hub data."""
        super().__post_init__()
        if not self.name:
            self.name = "Hub"

    def __repr__(self) -> str:
        """String representation of the hub."""
        return f"Hub({self.name}, {self.coordinates})"
