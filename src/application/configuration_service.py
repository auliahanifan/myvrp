from __future__ import annotations

import copy
import os
from dataclasses import replace
from typing import Any

import yaml

from src.application.contracts import AppConfigSnapshot
from src.models.hub_config import MultiHubConfig
from src.models.location import Depot
from src.models.vehicle import Vehicle, VehicleFleet
from src.utils.yaml_parser import YAMLParser


class ConfigurationService:
    def __init__(self, yaml_parser_cls=YAMLParser):
        self.yaml_parser_cls = yaml_parser_cls

    def load_snapshot(self, config_path: str = "conf.yaml") -> AppConfigSnapshot:
        parser = self.yaml_parser_cls(config_path)
        fleet = parser.parse()
        return AppConfigSnapshot(
            fleet=fleet,
            vehicle_config=self.fleet_to_config_dict(fleet),
            depot=self.get_depot_from_env(),
            hubs_config=self._get_hubs_from_parser(parser),
            cache_config=parser.get_cache_config(),
            solver_config=parser.get_config(),
        )

    def with_vehicle_config(
        self, snapshot: AppConfigSnapshot, vehicle_config: dict[str, Any]
    ) -> AppConfigSnapshot:
        fleet = self.config_dict_to_fleet(vehicle_config)
        return replace(
            snapshot,
            fleet=fleet,
            vehicle_config=copy.deepcopy(vehicle_config),
        )

    def fleet_to_config_dict(self, fleet: VehicleFleet) -> dict[str, Any]:
        vehicles = []
        for vehicle, count, unlimited in fleet.vehicle_types:
            vehicle_config = {
                "name": vehicle.name,
                "capacity": vehicle.capacity,
                "cost_per_km": vehicle.cost_per_km,
                "fixed_count": count,
                "unlimited": unlimited,
            }
            if vehicle.max_capacity is not None:
                vehicle_config["max_capacity"] = vehicle.max_capacity
            vehicles.append(vehicle_config)

        return {
            "vehicles": vehicles,
            "routing": {
                "return_to_depot": fleet.return_to_depot,
                "priority_time_tolerance": fleet.priority_time_tolerance,
                "non_priority_time_tolerance": fleet.non_priority_time_tolerance,
                "multiple_trips": fleet.multiple_trips,
                "relax_time_windows": fleet.relax_time_windows,
                "time_window_relaxation_minutes": fleet.time_window_relaxation_minutes,
            },
        }

    def config_dict_to_fleet(self, config: dict[str, Any]) -> VehicleFleet:
        if not config.get("vehicles"):
            raise ValueError("At least one vehicle type is required")

        vehicle_types = []
        for vehicle_config in config["vehicles"]:
            name = vehicle_config.get("name", "").strip()
            if not name:
                raise ValueError("Vehicle name is required")
            capacity = float(vehicle_config.get("capacity", 0))
            if capacity <= 0:
                raise ValueError(f"Vehicle {name}: Capacity must be positive")
            if vehicle_config.get("cost_per_km", 0) < 0:
                raise ValueError(f"Vehicle {name}: Rate must be non-negative")
            if vehicle_config.get("fixed_count", 0) <= 0:
                raise ValueError(f"Vehicle {name}: Count must be positive")
            max_capacity = vehicle_config.get("max_capacity")
            if max_capacity is None and self._is_motor_vehicle(name):
                max_capacity = 120.0
            if max_capacity is not None:
                max_capacity = float(max_capacity)
                if max_capacity < capacity:
                    raise ValueError(
                        f"Vehicle {name}: Max capacity must be greater than or equal to capacity"
                    )

            vehicle = Vehicle(
                name=name,
                capacity=capacity,
                cost_per_km=float(vehicle_config["cost_per_km"]),
                max_capacity=max_capacity,
                fixed_cost=float(vehicle_config["cost_per_km"]) * 10,
            )
            vehicle_types.append(
                (
                    vehicle,
                    int(vehicle_config["fixed_count"]),
                    bool(vehicle_config.get("unlimited", False)),
                )
            )

        routing = config.get("routing", {})
        return VehicleFleet(
            vehicle_types=vehicle_types,
            return_to_depot=routing.get("return_to_depot", True),
            priority_time_tolerance=routing.get("priority_time_tolerance", 0),
            non_priority_time_tolerance=routing.get("non_priority_time_tolerance", 60),
            multiple_trips=routing.get("multiple_trips", True),
            relax_time_windows=routing.get("relax_time_windows", False),
            time_window_relaxation_minutes=routing.get("time_window_relaxation_minutes", 0),
        )

    def export_config_yaml(self, vehicle_config: dict[str, Any]) -> str:
        return yaml.dump(vehicle_config, default_flow_style=False, allow_unicode=True)

    def get_depot_from_env(self) -> Depot:
        return Depot(
            name=os.getenv("DEPOT_NAME", "Segarloka Warehouse"),
            coordinates=(
                float(os.getenv("DEPOT_LATITUDE", "-6.2088")),
                float(os.getenv("DEPOT_LONGITUDE", "106.8456")),
            ),
            address=os.getenv("DEPOT_ADDRESS", "Jakarta, Indonesia"),
        )

    def _get_hubs_from_parser(self, parser: YAMLParser) -> MultiHubConfig:
        try:
            return parser.get_hubs_config()
        except Exception:
            return MultiHubConfig(enabled=False)

    def _is_motor_vehicle(self, name: str) -> bool:
        return "motor" in name.lower()
