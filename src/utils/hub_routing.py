"""
Hub routing logic for two-tier delivery system.
Determines which orders should be routed via hub based on zones and optimization.
Supports multi-hub configurations with zone-based and nearest-hub routing.
"""
from typing import List, Tuple, Dict, Optional
from math import radians, cos, sin, asin, sqrt
from ..models.order import Order
from ..models.location import Hub, Depot
from ..models.hub_config import MultiHubConfig, HubConfig


class HubRoutingManager:
    """
    Manages two-tier routing: Blind Van (DEPOT -> HUB) and Sepeda Motor (HUB -> Customer).

    Logic:
    1. Orders from specified zones are routed via hub (zone-based)
    2. Other orders can be routed directly from depot or via hub based on optimization
    """

    def __init__(
        self,
        hub: Hub,
        depot: Depot,
        zones_via_hub: List[str],
        blind_van_arrival_time: int = 360,  # 06:00 = 360 minutes
        motor_start_time: int = 360,  # 06:00 = 360 minutes
    ):
        """
        Initialize hub routing manager.

        Args:
            hub: Hub location object
            depot: Depot location object
            zones_via_hub: List of zones/cities that must route via hub (case-insensitive)
            blind_van_arrival_time: Time blind van arrives at hub (minutes from midnight)
            motor_start_time: Earliest time sepeda motor can deliver (minutes from midnight)
        """
        self.hub = hub
        self.depot = depot
        self.zones_via_hub = [z.upper() for z in zones_via_hub]  # Normalize to uppercase
        self.blind_van_arrival_time = blind_van_arrival_time
        self.motor_start_time = motor_start_time

    def should_route_via_hub(self, order: Order) -> bool:
        """
        Determine if an order should be routed via hub based on zone.

        Args:
            order: Order object

        Returns:
            True if order should route via hub, False otherwise
        """
        if not order.kota:
            return False

        # Check if order's city/kecamatan is in hub zones
        order_zone = order.kota.upper()
        return order_zone in self.zones_via_hub

    def classify_orders(self, orders: List[Order]) -> Tuple[List[Order], List[Order]]:
        """
        Classify orders into hub-route and direct-route based on zones.

        Args:
            orders: List of orders

        Returns:
            Tuple of (hub_orders, direct_orders)
        """
        hub_orders = []
        direct_orders = []

        for order in orders:
            if self.should_route_via_hub(order):
                hub_orders.append(order)
            else:
                direct_orders.append(order)

        return hub_orders, direct_orders

    def get_hub_routing_summary(self, orders: List[Order]) -> Dict:
        """
        Get summary of hub routing classification.

        Args:
            orders: List of orders

        Returns:
            Dictionary with routing summary
        """
        hub_orders, direct_orders = self.classify_orders(orders)

        hub_weight = sum(o.load_weight_in_kg for o in hub_orders)
        direct_weight = sum(o.load_weight_in_kg for o in direct_orders)

        return {
            "total_orders": len(orders),
            "hub_orders_count": len(hub_orders),
            "direct_orders_count": len(direct_orders),
            "hub_total_weight_kg": hub_weight,
            "direct_total_weight_kg": direct_weight,
            "hub_percentage": (len(hub_orders) / len(orders) * 100) if orders else 0,
            "hub_zones": self.zones_via_hub,
        }


class MultiHubRoutingManager:
    """
    Manages multi-hub routing for two-tier delivery system.

    Supports 0 to N hubs with:
    - Zone-based routing (priority): Orders from specified zones go to their assigned hub
    - Nearest hub fallback: Orders from unassigned zones go to geographically nearest hub
    - Direct depot routing: Orders can be routed directly from depot (no hub)

    Usage:
        manager = MultiHubRoutingManager(multi_hub_config, depot)
        classified = manager.classify_orders(orders)
        # Returns: {"hub_utara": [order1, order2], "hub_selatan": [order3], "DEPOT": [order4]}
    """

    DIRECT_KEY = "DEPOT"  # Key for orders routed directly from depot

    def __init__(
        self,
        multi_hub_config: MultiHubConfig,
        depot: Depot,
    ):
        """
        Initialize multi-hub routing manager.

        Args:
            multi_hub_config: MultiHubConfig with all hub configurations
            depot: Depot location object
        """
        self.config = multi_hub_config
        self.depot = depot
        self.zones_to_hub = multi_hub_config.get_zones_to_hub_mapping()

    @property
    def is_zero_hub_mode(self) -> bool:
        """Check if no hubs are configured."""
        return self.config.is_zero_hub_mode

    @property
    def num_hubs(self) -> int:
        """Get number of configured hubs."""
        return self.config.num_hubs

    def get_hub_for_order(self, order: Order) -> Optional[str]:
        """
        Determine which hub an order should be routed through.

        Priority:
        1. Zone-based mapping (if order's zone is configured for a hub)
        2. Nearest hub fallback (if unassigned_zone_behavior is "nearest")
        3. Direct from depot (return None)

        Args:
            order: Order object

        Returns:
            hub_id string or None if should go directly from DEPOT
        """
        if self.config.is_zero_hub_mode:
            return None

        # Get order zone (kota field)
        if order.kota:
            zone = order.kota.upper()

            # Priority 1: Zone-based mapping
            if zone in self.zones_to_hub:
                return self.zones_to_hub[zone]

        # Priority 2: Nearest hub fallback (if configured)
        if self.config.unassigned_zone_behavior == "nearest":
            return self._get_nearest_hub(order)

        # Default: Direct from depot
        return None

    def _get_nearest_hub(self, order: Order) -> Optional[str]:
        """
        Find the nearest hub to an order by Haversine distance.

        Args:
            order: Order object with coordinates

        Returns:
            hub_id of nearest hub or None if no hubs configured
        """
        if not self.config.hubs:
            return None

        min_distance = float('inf')
        nearest_hub_id = None

        for hub_config in self.config.hubs:
            distance = self._haversine_distance(
                order.coordinates,
                hub_config.hub.coordinates
            )
            if distance < min_distance:
                min_distance = distance
                nearest_hub_id = hub_config.hub_id

        return nearest_hub_id

    def _haversine_distance(
        self,
        coord1: Tuple[float, float],
        coord2: Tuple[float, float]
    ) -> float:
        """
        Calculate distance between two coordinates in kilometers.

        Args:
            coord1: (latitude, longitude) tuple
            coord2: (latitude, longitude) tuple

        Returns:
            Distance in kilometers
        """
        lat1, lon1 = radians(coord1[0]), radians(coord1[1])
        lat2, lon2 = radians(coord2[0]), radians(coord2[1])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        return 2 * 6371 * asin(sqrt(a))  # Earth radius = 6371 km

    def classify_orders(self, orders: List[Order]) -> Dict[str, List[Order]]:
        """
        Classify orders by their destination hub.

        Args:
            orders: List of orders to classify

        Returns:
            Dictionary mapping hub_id (or "DEPOT") to list of orders
            Example: {"hub_utara": [o1, o2], "hub_selatan": [o3], "DEPOT": [o4]}
        """
        classified: Dict[str, List[Order]] = {}

        for order in orders:
            hub_id = self.get_hub_for_order(order)
            key = hub_id if hub_id else self.DIRECT_KEY

            if key not in classified:
                classified[key] = []
            classified[key].append(order)

        return classified

    def get_hub_orders(self, orders: List[Order]) -> List[Order]:
        """
        Get all orders that go through any hub (not direct from depot).

        Args:
            orders: List of orders

        Returns:
            List of orders routed through hubs
        """
        classified = self.classify_orders(orders)
        hub_orders = []
        for key, order_list in classified.items():
            if key != self.DIRECT_KEY:
                hub_orders.extend(order_list)
        return hub_orders

    def get_direct_orders(self, orders: List[Order]) -> List[Order]:
        """
        Get all orders that go directly from depot (no hub).

        Args:
            orders: List of orders

        Returns:
            List of orders routed directly from depot
        """
        classified = self.classify_orders(orders)
        return classified.get(self.DIRECT_KEY, [])

    def classify_orders_zone_based(self, orders: List[Order]) -> Dict[str, List[Order]]:
        """
        Classify orders using only zone-based assignment (no dynamic optimization).

        This is the pure zone-based classification that can be used as baseline
        for hybrid dynamic assignment comparison.

        Args:
            orders: List of orders to classify

        Returns:
            Dictionary mapping hub_id (or "DEPOT") to list of orders
        """
        return self.classify_orders(orders)

    def get_routing_summary(self, orders: List[Order]) -> Dict:
        """
        Get summary of hub routing classification.

        Args:
            orders: List of orders

        Returns:
            Dictionary with routing summary including per-hub breakdown
        """
        classified = self.classify_orders(orders)

        summary = {
            "total_orders": len(orders),
            "total_hubs_used": len([k for k in classified.keys() if k != self.DIRECT_KEY]),
            "hub_breakdown": {},
            "direct_orders_count": len(classified.get(self.DIRECT_KEY, [])),
            "direct_weight_kg": sum(
                o.load_weight_in_kg for o in classified.get(self.DIRECT_KEY, [])
            ),
        }

        total_hub_weight = 0.0
        total_hub_orders = 0
        for hub_id, hub_orders in classified.items():
            if hub_id == self.DIRECT_KEY:
                continue
            weight = sum(o.load_weight_in_kg for o in hub_orders)
            total_hub_weight += weight
            total_hub_orders += len(hub_orders)

            hub_config = self.config.get_hub_by_id(hub_id)
            hub_name = hub_config.hub.name if hub_config else hub_id

            summary["hub_breakdown"][hub_id] = {
                "name": hub_name,
                "count": len(hub_orders),
                "weight_kg": weight,
                "zones": hub_config.zones_via_hub if hub_config else [],
            }

        summary["total_hub_orders"] = total_hub_orders
        summary["total_hub_weight_kg"] = total_hub_weight
        summary["hub_percentage"] = (
            (total_hub_orders / len(orders) * 100) if orders else 0
        )

        return summary


def parse_hub_config(config_dict: Optional[Dict]) -> Optional[Dict]:
    """
    Parse hub configuration from YAML dictionary.

    Args:
        config_dict: Hub configuration dictionary from YAML

    Returns:
        Parsed hub config or None if hub not enabled
    """
    if not config_dict or not config_dict.get("enabled", False):
        return None

    try:
        location = config_dict.get("location", {})
        hub_location = Hub(
            name=location.get("name", "Hub"),
            coordinates=(
                location.get("latitude", -6.164667),
                location.get("longitude", 106.871609),
            ),
            address=location.get("address", ""),
        )

        zones_via_hub = config_dict.get("zones_via_hub", [])
        if not isinstance(zones_via_hub, list):
            zones_via_hub = [zones_via_hub]

        blind_van_schedule = config_dict.get("blind_van_schedule", {})
        # Convert departure time HH:MM to minutes
        departure_str = blind_van_schedule.get("departure_time", "05:30")
        arrival_str = blind_van_schedule.get("arrival_time", "06:00")

        blind_van_departure = time_str_to_minutes(departure_str)
        blind_van_arrival = time_str_to_minutes(arrival_str)

        motor_routing = config_dict.get("motor_routing", {})
        motor_start_str = motor_routing.get("start_delivery_after", "06:00")
        motor_start_time = time_str_to_minutes(motor_start_str)

        return {
            "hub": hub_location,
            "zones_via_hub": zones_via_hub,
            "blind_van_departure": blind_van_departure,
            "blind_van_arrival": blind_van_arrival,
            "motor_start_time": motor_start_time,
            "can_depart_from_depot": motor_routing.get("can_depart_from_depot", True),
            "can_depart_from_hub": motor_routing.get("can_depart_from_hub", True),
        }
    except Exception as e:
        raise ValueError(f"Error parsing hub configuration: {str(e)}")


def time_str_to_minutes(time_str: str) -> int:
    """
    Convert HH:MM format to minutes from midnight.

    Args:
        time_str: Time string in HH:MM format

    Returns:
        Minutes from midnight

    Raises:
        ValueError: If time format is invalid
    """
    try:
        parts = time_str.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid time format: {time_str}")
        hours = int(parts[0])
        minutes = int(parts[1])
        if not (0 <= hours < 24 and 0 <= minutes < 60):
            raise ValueError(f"Invalid time values: {time_str}")
        return hours * 60 + minutes
    except (ValueError, IndexError) as e:
        raise ValueError(f"Invalid time format '{time_str}': {str(e)}")


def minutes_to_time_str(minutes: int) -> str:
    """
    Convert minutes from midnight to HH:MM format.

    Args:
        minutes: Minutes from midnight

    Returns:
        Time string in HH:MM format
    """
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"
