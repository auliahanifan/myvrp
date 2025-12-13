"""
Hub configuration models for multi-hub VRP routing.

Supports 0 to N hubs with zone-based routing and nearest hub fallback.
Supports per-hub blind van modes (Mode A: consolidation only, Mode B: consolidation + delivery).
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional

from .location import Hub


class BlindVanMode(Enum):
    """Blind van operational modes for each hub."""
    CONSOLIDATION_ONLY = "consolidation_only"  # Mode A: only consolidation, no delivery
    CONSOLIDATION_WITH_DELIVERY = "consolidation_with_delivery"  # Mode B: consolidation + en-route delivery


@dataclass
class EnRouteDeliveryConfig:
    """Configuration for en-route delivery (Mode B)."""
    max_stops: int = 0  # Max delivery stops before reaching hub (0 = disabled)
    max_detour_minutes: int = 10  # Max time deviation from direct route
    max_detour_km: float = 5.0  # Max distance deviation from direct route
    reserve_capacity_kg: float = 100.0  # Reserved capacity for hub consolidation


@dataclass
class HubBlindVanConfig:
    """Per-hub blind van configuration."""
    mode: BlindVanMode = BlindVanMode.CONSOLIDATION_ONLY
    en_route_delivery: Optional[EnRouteDeliveryConfig] = None

    def __post_init__(self):
        # If mode is Mode B but no en_route_delivery config, create default
        if self.mode == BlindVanMode.CONSOLIDATION_WITH_DELIVERY and self.en_route_delivery is None:
            self.en_route_delivery = EnRouteDeliveryConfig()

    @property
    def is_delivery_enabled(self) -> bool:
        """Check if en-route delivery is enabled for this hub."""
        return (
            self.mode == BlindVanMode.CONSOLIDATION_WITH_DELIVERY and
            self.en_route_delivery is not None and
            self.en_route_delivery.max_stops > 0
        )


@dataclass
class SourceAssignmentConfig:
    """Configuration for dynamic source assignment."""
    mode: str = "zone_based"  # "zone_based", "dynamic", "hybrid"
    min_cost_advantage_percent: float = 10.0  # Switch source only if X% better
    distance_weight: float = 1.0  # Weight for distance in cost calculation
    time_weight: float = 0.5  # Weight for travel time in cost calculation


@dataclass
class HubConfig:
    """Configuration for a single hub with zone mappings and blind van mode."""
    hub: Hub
    hub_id: str
    zones_via_hub: List[str] = field(default_factory=list)
    blind_van_config: HubBlindVanConfig = field(default_factory=HubBlindVanConfig)

    def __post_init__(self):
        # Normalize zones to uppercase
        self.zones_via_hub = [z.upper() for z in self.zones_via_hub]


@dataclass
class MultiHubConfig:
    """Configuration for multiple hubs."""
    hubs: List[HubConfig] = field(default_factory=list)
    enabled: bool = False
    blind_van_departure: int = 330  # 05:30 in minutes from midnight
    blind_van_arrival: int = 360    # 06:00 in minutes from midnight (hub arrival deadline)
    motor_start_time: int = 360     # 06:00 in minutes from midnight
    unassigned_zone_behavior: str = "nearest"  # "nearest" or "depot"
    blind_van_vehicle_name: str = "Blind Van"
    blind_van_return_to_depot: bool = False  # If false, blind van can end at last hub
    source_assignment: SourceAssignmentConfig = field(default_factory=SourceAssignmentConfig)

    @property
    def num_hubs(self) -> int:
        """Number of configured hubs."""
        return len(self.hubs)

    @property
    def is_zero_hub_mode(self) -> bool:
        """True if no hubs are configured or hub routing is disabled."""
        return not self.enabled or self.num_hubs == 0

    def get_hub_by_id(self, hub_id: str) -> Optional[HubConfig]:
        """Get hub configuration by hub_id."""
        for hub_config in self.hubs:
            if hub_config.hub_id == hub_id:
                return hub_config
        return None

    def get_zones_to_hub_mapping(self) -> Dict[str, str]:
        """
        Returns mapping of zone names to hub IDs.

        Example: {"JAKARTA UTARA": "hub_utara", "JAKARTA SELATAN": "hub_selatan"}
        """
        mapping = {}
        for hub_config in self.hubs:
            for zone in hub_config.zones_via_hub:
                mapping[zone.upper()] = hub_config.hub_id
        return mapping

    def get_all_hub_ids(self) -> List[str]:
        """Get list of all hub IDs."""
        return [h.hub_id for h in self.hubs]

    def get_all_hubs(self) -> List[Hub]:
        """Get list of all Hub objects."""
        return [h.hub for h in self.hubs]

    def get_hubs_with_delivery(self) -> List[HubConfig]:
        """Get list of hubs with en-route delivery enabled (Mode B with max_stops > 0)."""
        return [h for h in self.hubs if h.blind_van_config.is_delivery_enabled]

    def get_hubs_consolidation_only(self) -> List[HubConfig]:
        """Get list of hubs with consolidation only (Mode A or Mode B with max_stops = 0)."""
        return [h for h in self.hubs if not h.blind_van_config.is_delivery_enabled]

    def has_any_delivery_enabled(self) -> bool:
        """Check if any hub has en-route delivery enabled."""
        return any(h.blind_van_config.is_delivery_enabled for h in self.hubs)


class HubIndexManager:
    """
    Manages dynamic matrix indexing for multi-hub scenarios.

    Matrix structure:
    - Index 0: DEPOT
    - Index 1 to N: HUB_1, HUB_2, ..., HUB_N
    - Index N+1 onwards: Customers

    Example with 2 hubs:
        [DEPOT, HUB_1, HUB_2, cust_1, cust_2, ...]
           0      1      2      3       4
    """

    DEPOT_INDEX = 0

    def __init__(self, hub_ids: List[str]):
        """
        Initialize index manager.

        Args:
            hub_ids: List of hub IDs in order they appear in the matrix
        """
        self.hub_ids = hub_ids
        self._hub_index_map: Dict[str, int] = {
            hub_id: i + 1 for i, hub_id in enumerate(hub_ids)
        }
        self._customer_start_index = len(hub_ids) + 1

    def get_depot_index(self) -> int:
        """Get matrix index for DEPOT (always 0)."""
        return self.DEPOT_INDEX

    def get_hub_index(self, hub_id: str) -> int:
        """
        Get matrix index for a specific hub.

        Args:
            hub_id: The hub identifier

        Returns:
            Matrix index for the hub

        Raises:
            ValueError: If hub_id is not found
        """
        if hub_id not in self._hub_index_map:
            raise ValueError(f"Unknown hub_id: {hub_id}. Available: {list(self._hub_index_map.keys())}")
        return self._hub_index_map[hub_id]

    def get_customer_index(self, order_idx: int) -> int:
        """
        Convert order index (0-based in orders list) to matrix index.

        Args:
            order_idx: Index of order in the orders list (0-based)

        Returns:
            Matrix index for the customer
        """
        return self._customer_start_index + order_idx

    def get_all_hub_indices(self) -> List[int]:
        """Get list of all hub indices in the matrix."""
        return list(self._hub_index_map.values())

    @property
    def customer_start_index(self) -> int:
        """Index where customers start in the matrix."""
        return self._customer_start_index

    @property
    def num_hubs(self) -> int:
        """Number of hubs managed."""
        return len(self.hub_ids)

    def get_hub_id_by_index(self, index: int) -> Optional[str]:
        """Get hub_id from matrix index."""
        for hub_id, idx in self._hub_index_map.items():
            if idx == index:
                return hub_id
        return None
