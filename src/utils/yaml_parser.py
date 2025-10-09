"""
YAML parser for vehicle configuration.
Parses vehicle config YAML files and creates Vehicle objects with validation.
"""
import yaml
from typing import List
from ..models.vehicle import Vehicle, VehicleFleet


class YAMLParserError(Exception):
    """Custom exception for YAML parsing errors."""
    pass


class YAMLParser:
    """
    Parser for vehicle configuration YAML files.

    Expected format:
    ```yaml
    vehicles:
      - name: "L300"
        capacity: 800  # kg
        cost_per_km: 5000  # Rupiah
      - name: "Granmax"
        capacity: 500
        cost_per_km: 3500
    unlimited: true  # optional, defaults to true
    ```
    """

    def __init__(self, yaml_path: str):
        """
        Initialize YAML parser.

        Args:
            yaml_path: Path to YAML file
        """
        self.yaml_path = yaml_path
        self.data = None

    def parse(self) -> VehicleFleet:
        """
        Parse YAML file and return VehicleFleet object.

        Returns:
            VehicleFleet object

        Raises:
            YAMLParserError: If parsing fails or validation errors occur
        """
        try:
            with open(self.yaml_path, "r") as f:
                self.data = yaml.safe_load(f)
        except FileNotFoundError:
            raise YAMLParserError(f"YAML file not found: {self.yaml_path}")
        except yaml.YAMLError as e:
            raise YAMLParserError(f"Error parsing YAML file: {str(e)}")
        except Exception as e:
            raise YAMLParserError(f"Error reading YAML file: {str(e)}")

        # Validate structure
        if not isinstance(self.data, dict):
            raise YAMLParserError("YAML file must contain a dictionary")

        if "vehicles" not in self.data:
            raise YAMLParserError("YAML file must contain 'vehicles' key")

        # Parse vehicles
        vehicles = self._parse_vehicles()

        # Parse unlimited flag
        unlimited = self.data.get("unlimited", True)
        if not isinstance(unlimited, bool):
            raise YAMLParserError("'unlimited' must be a boolean value")

        # Create fleet
        try:
            fleet = VehicleFleet(vehicle_types=vehicles, unlimited=unlimited)
        except Exception as e:
            raise YAMLParserError(f"Error creating vehicle fleet: {str(e)}")

        return fleet

    def _parse_vehicles(self) -> List[Vehicle]:
        """
        Parse vehicles list from YAML data.

        Returns:
            List of Vehicle objects

        Raises:
            YAMLParserError: If vehicle data is invalid
        """
        vehicles_data = self.data["vehicles"]

        if not isinstance(vehicles_data, list):
            raise YAMLParserError("'vehicles' must be a list")

        if not vehicles_data:
            raise YAMLParserError("'vehicles' list cannot be empty")

        vehicles = []
        for idx, vehicle_data in enumerate(vehicles_data):
            try:
                vehicle = self._parse_vehicle(vehicle_data, idx)
                vehicles.append(vehicle)
            except Exception as e:
                raise YAMLParserError(f"Error parsing vehicle {idx}: {str(e)}")

        return vehicles

    def _parse_vehicle(self, vehicle_data: dict, idx: int) -> Vehicle:
        """
        Parse a single vehicle from YAML data.

        Args:
            vehicle_data: Vehicle dictionary
            idx: Vehicle index (for error messages)

        Returns:
            Vehicle object

        Raises:
            ValueError: If vehicle data is invalid
        """
        if not isinstance(vehicle_data, dict):
            raise ValueError("Vehicle data must be a dictionary")

        # Check required fields
        required_fields = ["name", "capacity", "cost_per_km"]
        for field in required_fields:
            if field not in vehicle_data:
                raise ValueError(f"Missing required field: {field}")

        # Parse fields
        name = vehicle_data["name"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Vehicle name must be a non-empty string")

        try:
            capacity = float(vehicle_data["capacity"])
        except (ValueError, TypeError):
            raise ValueError(f"Invalid capacity: {vehicle_data['capacity']}")

        try:
            cost_per_km = float(vehicle_data["cost_per_km"])
        except (ValueError, TypeError):
            raise ValueError(f"Invalid cost_per_km: {vehicle_data['cost_per_km']}")

        # Create Vehicle object (validation happens in __post_init__)
        vehicle = Vehicle(
            name=name.strip(),
            capacity=capacity,
            cost_per_km=cost_per_km,
        )

        return vehicle

    def get_summary(self) -> dict:
        """
        Get summary of vehicle configuration.

        Returns:
            Dictionary with summary stats
        """
        if self.data is None:
            return {}

        vehicles = self.data.get("vehicles", [])
        return {
            "num_vehicle_types": len(vehicles),
            "unlimited_fleet": self.data.get("unlimited", True),
            "total_capacity": sum(v.get("capacity", 0) for v in vehicles),
            "vehicle_names": [v.get("name", "Unknown") for v in vehicles],
        }
