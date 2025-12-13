"""
YAML parser for vehicle configuration.
Parses vehicle config YAML files and creates Vehicle objects with validation.
"""
import warnings
import yaml
from typing import List, Optional, Dict
from ..models.vehicle import Vehicle, VehicleFleet
from ..models.location import Hub
from ..models.hub_config import (
    HubConfig,
    MultiHubConfig,
    BlindVanMode,
    EnRouteDeliveryConfig,
    HubBlindVanConfig,
    SourceAssignmentConfig,
)
from .hub_routing import parse_hub_config, time_str_to_minutes


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
        relax_time_windows = routing_config.get("relax_time_windows", False)
        time_window_relaxation_minutes = routing_config.get("time_window_relaxation_minutes", 0)

        # Create fleet
        try:
            fleet = VehicleFleet(
                vehicle_types=vehicle_types,
                return_to_depot=return_to_depot,
                priority_time_tolerance=priority_time_tolerance,
                non_priority_time_tolerance=non_priority_time_tolerance,
                multiple_trips=multiple_trips,
                relax_time_windows=relax_time_windows,
                time_window_relaxation_minutes=time_window_relaxation_minutes,
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

    def get_hub_config(self) -> Optional[Dict]:
        """
        Parse hub configuration from YAML (legacy single-hub format).

        DEPRECATED: Use get_hubs_config() for multi-hub support.

        Returns:
            Dictionary with hub configuration or None if hub not enabled

        Raises:
            YAMLParserError: If hub configuration is invalid
        """
        if self.data is None:
            return None

        hub_config = self.data.get("hub", {})
        if not hub_config.get("enabled", False):
            return None

        try:
            return parse_hub_config(hub_config)
        except ValueError as e:
            raise YAMLParserError(f"Error parsing hub configuration: {str(e)}")

    def get_hubs_config(self) -> MultiHubConfig:
        """
        Parse multi-hub configuration from YAML.

        Supports both new multi-hub format and legacy single-hub format.
        New format uses 'hubs.locations[]', legacy uses 'hub.location'.

        Returns:
            MultiHubConfig object (with is_zero_hub_mode=True if no hubs configured)

        Raises:
            YAMLParserError: If hub configuration is invalid
        """
        if self.data is None:
            return MultiHubConfig(enabled=False)

        # Check for new multi-hub format first
        hubs_config = self.data.get("hubs", {})
        if hubs_config and hubs_config.get("locations"):
            return self._parse_multi_hub_config(hubs_config)

        # Fall back to legacy single-hub format
        hub_config = self.data.get("hub", {})
        if hub_config and hub_config.get("enabled", False):
            return self._convert_legacy_hub_config(hub_config)

        # No hubs configured
        return MultiHubConfig(enabled=False)

    def _parse_multi_hub_config(self, config: Dict) -> MultiHubConfig:
        """
        Parse new multi-hub format from YAML.

        Args:
            config: The 'hubs' section from YAML

        Returns:
            MultiHubConfig object
        """
        try:
            hub_configs = []
            for loc in config.get("locations", []):
                hub = Hub(
                    name=loc.get("name", "Hub"),
                    hub_id=loc.get("id", ""),
                    coordinates=(
                        loc.get("latitude", 0.0),
                        loc.get("longitude", 0.0),
                    ),
                    address=loc.get("address", ""),
                )

                # Parse per-hub blind van configuration
                blind_van_cfg = self._parse_hub_blind_van_config(loc.get("blind_van", {}))

                hub_config = HubConfig(
                    hub=hub,
                    hub_id=loc.get("id", hub.hub_id),
                    zones_via_hub=loc.get("zones_via_hub", []),
                    blind_van_config=blind_van_cfg,
                )
                hub_configs.append(hub_config)

            schedule = config.get("blind_van_schedule", {})
            motor = config.get("motor_routing", {})

            # Parse source assignment configuration
            source_assignment_cfg = self._parse_source_assignment_config(
                config.get("source_assignment", {})
            )

            # Support both old 'arrival_time' and new 'hub_arrival_deadline'
            hub_arrival = schedule.get("hub_arrival_deadline") or schedule.get("arrival_time", "06:00")

            return MultiHubConfig(
                hubs=hub_configs,
                enabled=config.get("enabled", True) and len(hub_configs) > 0,
                blind_van_departure=time_str_to_minutes(schedule.get("departure_time", "05:30")),
                blind_van_arrival=time_str_to_minutes(hub_arrival),
                motor_start_time=time_str_to_minutes(motor.get("start_delivery_after", "06:00")),
                unassigned_zone_behavior=config.get("unassigned_zone_behavior", "nearest"),
                blind_van_vehicle_name=schedule.get("vehicle_name", "Blind Van"),
                blind_van_return_to_depot=schedule.get("return_to_depot", False),
                source_assignment=source_assignment_cfg,
            )
        except Exception as e:
            raise YAMLParserError(f"Error parsing multi-hub configuration: {str(e)}")

    def _parse_hub_blind_van_config(self, config: Dict) -> HubBlindVanConfig:
        """
        Parse per-hub blind van configuration.

        Args:
            config: The 'blind_van' section for a hub

        Returns:
            HubBlindVanConfig object
        """
        if not config:
            return HubBlindVanConfig()

        # Parse mode
        mode_str = config.get("mode", "consolidation_only")
        try:
            mode = BlindVanMode(mode_str)
        except ValueError:
            mode = BlindVanMode.CONSOLIDATION_ONLY

        # Parse en-route delivery config if present
        en_route_cfg = None
        if mode == BlindVanMode.CONSOLIDATION_WITH_DELIVERY:
            en_route_data = config.get("en_route_delivery", {})
            en_route_cfg = EnRouteDeliveryConfig(
                max_stops=en_route_data.get("max_stops", 0),
                max_detour_minutes=en_route_data.get("max_detour_minutes", 10),
                max_detour_km=en_route_data.get("max_detour_km", 5.0),
                reserve_capacity_kg=en_route_data.get("reserve_capacity_kg", 100.0),
            )

        return HubBlindVanConfig(mode=mode, en_route_delivery=en_route_cfg)

    def _parse_source_assignment_config(self, config: Dict) -> SourceAssignmentConfig:
        """
        Parse source assignment configuration.

        Args:
            config: The 'source_assignment' section from YAML

        Returns:
            SourceAssignmentConfig object
        """
        if not config:
            return SourceAssignmentConfig()

        dynamic_cfg = config.get("dynamic", {})
        weights = dynamic_cfg.get("weights", {})

        return SourceAssignmentConfig(
            mode=config.get("mode", "zone_based"),
            min_cost_advantage_percent=dynamic_cfg.get("min_cost_advantage_percent", 10.0),
            distance_weight=weights.get("distance", 1.0),
            time_weight=weights.get("time", 0.5),
        )

    def _convert_legacy_hub_config(self, config: Dict) -> MultiHubConfig:
        """
        Convert legacy single-hub format to new multi-hub format.

        Args:
            config: The 'hub' section from YAML (legacy format)

        Returns:
            MultiHubConfig object with single hub
        """
        warnings.warn(
            "Legacy single-hub config format ('hub.location') detected. "
            "Please migrate to new 'hubs.locations[]' format.",
            DeprecationWarning,
            stacklevel=3,
        )

        try:
            location = config.get("location", {})
            hub = Hub(
                name=location.get("name", "Hub"),
                hub_id="hub_default",
                coordinates=(
                    location.get("latitude", 0.0),
                    location.get("longitude", 0.0),
                ),
                address=location.get("address", ""),
            )

            hub_config = HubConfig(
                hub=hub,
                hub_id="hub_default",
                zones_via_hub=config.get("zones_via_hub", []),
            )

            schedule = config.get("blind_van_schedule", {})
            motor = config.get("motor_routing", {})

            return MultiHubConfig(
                hubs=[hub_config],
                enabled=True,
                blind_van_departure=time_str_to_minutes(schedule.get("departure_time", "05:30")),
                blind_van_arrival=time_str_to_minutes(schedule.get("arrival_time", "06:00")),
                motor_start_time=time_str_to_minutes(motor.get("start_delivery_after", "06:00")),
                unassigned_zone_behavior="depot",  # Legacy behavior: unassigned goes direct
                blind_van_vehicle_name=schedule.get("vehicle_name", "Blind Van"),
            )
        except Exception as e:
            raise YAMLParserError(f"Error converting legacy hub configuration: {str(e)}")

    def get_constraints_config(self) -> Dict:
        """
        Parse solver constraints configuration from YAML.

        Returns:
            Dictionary with constraints configuration
        """
        if self.data is None:
            return {}

        constraints_config = self.data.get("constraints", {})
        return {
            "enforce_time_windows": constraints_config.get("enforce_time_windows", True),
            "enforce_capacity": constraints_config.get("enforce_capacity", True),
            "enforce_city_limit": constraints_config.get("enforce_city_limit", True),
            "allow_dropped_orders": constraints_config.get("allow_dropped_orders", True),
        }

    def get_penalties_config(self) -> Dict:
        """
        Parse penalty values configuration from YAML.

        Returns:
            Dictionary with penalty values
        """
        if self.data is None:
            return {}

        penalties_config = self.data.get("penalties", {})
        return {
            "dropped_order": penalties_config.get("dropped_order", 1000000),
            "time_violation_per_minute": penalties_config.get("time_violation_per_minute", 100),
        }

    def get_debug_config(self) -> Dict:
        """
        Parse debug configuration from YAML.

        Returns:
            Dictionary with debug configuration
        """
        if self.data is None:
            return {}

        debug_config = self.data.get("debug", {})
        return {
            "enabled": debug_config.get("enabled", False),
            "log_level": debug_config.get("log_level", "INFO"),
            "save_distance_matrix": debug_config.get("save_distance_matrix", False),
            "save_solver_params": debug_config.get("save_solver_params", False),
        }

    def get_solver_config(self) -> Dict:
        """
        Parse solver configuration from YAML.

        Returns:
            Dictionary with solver configuration
        """
        if self.data is None:
            return {}

        solver_config = self.data.get("solver", {})
        return {
            "time_limit": solver_config.get("time_limit", 300),
            "optimization_strategy": solver_config.get("optimization_strategy", "balanced"),
            "metaheuristic": solver_config.get("metaheuristic", "GUIDED_LOCAL_SEARCH"),
            "guided_local_search": solver_config.get("guided_local_search", {
                "lambda_coefficient_minimize_vehicles": 0.1,
                "lambda_coefficient_minimize_cost": 0.2,
                "lambda_coefficient_balanced": 0.15,
            }),
            "solution_limit": solver_config.get("solution_limit", 50000),
            "lns_time_limit": solver_config.get("lns_time_limit", 1),
            "use_depth_first_search": solver_config.get("use_depth_first_search", False),
        }

    def get_config(self) -> Dict:
        """
        Get complete configuration dictionary.

        Returns:
            Dictionary with all configuration sections
        """
        if self.data is None:
            return {}

        return {
            "debug": self.get_debug_config(),
            "solver": self.get_solver_config(),
            "constraints": self.get_constraints_config(),
            "penalties": self.get_penalties_config(),
            "cache": self.get_cache_config(),
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
