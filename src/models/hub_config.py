"""
Hub configuration models for multi-hub VRP routing.

Supports 0 to N hubs with zone-based routing and nearest hub fallback.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from .location import Hub


@dataclass
class HubConfig:
    """Configuration for a single hub with zone mappings."""
    hub: Hub
    hub_id: str
    zones_via_hub: List[str] = field(default_factory=list)

    def __post_init__(self):
        # Normalize zones to uppercase
        self.zones_via_hub = [z.upper() for z in self.zones_via_hub]


@dataclass
class MultiHubConfig:
    """Configuration for multiple hubs."""
    hubs: List[HubConfig] = field(default_factory=list)
    enabled: bool = False
    blind_van_departure: int = 330  # 05:30 in minutes from midnight
    blind_van_arrival: int = 360    # 06:00 in minutes from midnight
    motor_start_time: int = 360     # 06:00 in minutes from midnight
    unassigned_zone_behavior: str = "nearest"  # "nearest" or "depot"
    blind_van_vehicle_name: str = "Blind Van"

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
