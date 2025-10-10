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
      - name: "Blind Van"
        capacity: 800  # kg
        cost_per_km: 5000  # Rupiah
        fixed_count: 1  # number of this vehicle type
        unlimited: false  # optional, if this type can spawn more
      - name: "Sepeda Motor"
        capacity: 80
        cost_per_km: 1500
        fixed_count: 15
        unlimited: true  # can add more on demand

    routing:
      return_to_depot: true
      priority_time_tolerance: 0
      non_priority_time_tolerance: 20
      multiple_trips: true
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

        # Parse vehicles with their counts
        vehicle_types = self._parse_vehicles()

        # Parse routing config
        routing_config = self.data.get("routing", {})
        return_to_depot = routing_config.get("return_to_depot", True)
        priority_time_tolerance = routing_config.get("priority_time_tolerance", 0)
        non_priority_time_tolerance = routing_config.get("non_priority_time_tolerance", 20)
        multiple_trips = routing_config.get("multiple_trips", True)

        # Create fleet
        try:
            fleet = VehicleFleet(
                vehicle_types=vehicle_types,
                return_to_depot=return_to_depot,
                priority_time_tolerance=priority_time_tolerance,
                non_priority_time_tolerance=non_priority_time_tolerance,
                multiple_trips=multiple_trips,
            )
        except Exception as e:
            raise YAMLParserError(f"Error creating vehicle fleet: {str(e)}")

        return fleet

    def get_cache_config(self) -> dict:
        """
        Parse cache configuration from YAML.

        Returns:
            Dictionary with cache configuration
        """
        if self.data is None:
            return {}

        cache_config = self.data.get("cache", {})
        return {
            "enabled": cache_config.get("enabled", True),
            "ttl_hours": cache_config.get("ttl_hours", 24),
            "directory": cache_config.get("directory", ".cache"),
        }

    def _parse_vehicles(self) -> List[tuple[Vehicle, int, bool]]:
        """
        Parse vehicles list from YAML data.

        Returns:
            List of tuples (Vehicle, count, unlimited)

        Raises:
            YAMLParserError: If vehicle data is invalid
        """
        vehicles_data = self.data["vehicles"]

        if not isinstance(vehicles_data, list):
            raise YAMLParserError("'vehicles' must be a list")

        if not vehicles_data:
            raise YAMLParserError("'vehicles' list cannot be empty")

        vehicle_types = []
        for idx, vehicle_data in enumerate(vehicles_data):
            try:
                vehicle, count, unlimited = self._parse_vehicle(vehicle_data, idx)
                vehicle_types.append((vehicle, count, unlimited))
            except Exception as e:
                raise YAMLParserError(f"Error parsing vehicle {idx}: {str(e)}")

        return vehicle_types

    def _parse_vehicle(self, vehicle_data: dict, idx: int) -> tuple[Vehicle, int, bool]:
        """
        Parse a single vehicle from YAML data.

        Args:
            vehicle_data: Vehicle dictionary
            idx: Vehicle index (for error messages)

        Returns:
            Tuple of (Vehicle object, count, unlimited)

        Raises:
            ValueError: If vehicle data is invalid
        """
        if not isinstance(vehicle_data, dict):
            raise ValueError("Vehicle data must be a dictionary")

        # Check required fields
        required_fields = ["name", "capacity", "cost_per_km", "fixed_count"]
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

        try:
            fixed_count = int(vehicle_data["fixed_count"])
            if fixed_count <= 0:
                raise ValueError("fixed_count must be positive")
        except (ValueError, TypeError):
            raise ValueError(f"Invalid fixed_count: {vehicle_data['fixed_count']}")

        # Parse unlimited flag (optional, defaults to False)
        unlimited = vehicle_data.get("unlimited", False)
        if not isinstance(unlimited, bool):
            raise ValueError("'unlimited' must be a boolean value")

        # Calculate fixed cost based on cost_per_km (higher cost = use first to minimize vehicles)
        fixed_cost = cost_per_km * 10  # Base fixed cost proportional to per-km cost

        # Create Vehicle object (validation happens in __post_init__)
        vehicle = Vehicle(
            name=name.strip(),
            capacity=capacity,
            cost_per_km=cost_per_km,
            fixed_cost=fixed_cost,
        )

        return vehicle, fixed_count, unlimited

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
