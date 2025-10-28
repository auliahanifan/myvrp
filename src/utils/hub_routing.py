"""
Hub routing logic for two-tier delivery system.
Determines which orders should be routed via hub based on zones and optimization.
"""
from typing import List, Tuple, Dict, Optional
from ..models.order import Order
from ..models.location import Hub, Depot


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
