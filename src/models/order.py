"""
Order model for VRP solver.
Represents a delivery order with all necessary information.
"""
from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional, Tuple


@dataclass
class Order:
    """
    Represents a single delivery order.

    Attributes:
        sale_order_id: Unique order identifier
        delivery_date: Date of delivery
        delivery_time: Expected delivery time (HH:MM format)
        load_weight_in_kg: Weight of the order in kilograms
        partner_id: Customer partner ID
        display_name: Customer display name
        alamat: Full delivery address
        coordinates: Tuple of (latitude, longitude)
        is_priority: Whether this is a priority order (default False)
    """
    sale_order_id: str
    delivery_date: str  # YYYY-MM-DD format
    delivery_time: str  # HH:MM format
    load_weight_in_kg: float
    partner_id: str
    display_name: str
    alamat: str
    coordinates: Tuple[float, float]  # (latitude, longitude)
    is_priority: bool = False

    def __post_init__(self):
        """Validate order data after initialization."""
        # Validate weight is positive
        if self.load_weight_in_kg <= 0:
            raise ValueError(f"Order {self.sale_order_id}: Weight must be positive")

        # Validate coordinates
        lat, lng = self.coordinates
        if not (-90 <= lat <= 90):
            raise ValueError(f"Order {self.sale_order_id}: Invalid latitude {lat}")
        if not (-180 <= lng <= 180):
            raise ValueError(f"Order {self.sale_order_id}: Invalid longitude {lng}")

        # Validate delivery_time format
        try:
            time.fromisoformat(self.delivery_time)
        except ValueError:
            raise ValueError(
                f"Order {self.sale_order_id}: Invalid time format '{self.delivery_time}'. "
                "Expected HH:MM"
            )

        # Validate delivery_date format
        try:
            datetime.strptime(self.delivery_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(
                f"Order {self.sale_order_id}: Invalid date format '{self.delivery_date}'. "
                "Expected YYYY-MM-DD"
            )

    @property
    def time_window_start(self) -> int:
        """
        Get time window start in minutes from midnight.
        For delivery at HH:MM, the earliest arrival is the delivery time.

        Returns:
            Minutes from midnight
        """
        t = time.fromisoformat(self.delivery_time)
        return t.hour * 60 + t.minute

    @property
    def time_window_end(self) -> int:
        """
        Get time window end in minutes from midnight.
        For delivery at HH:MM, the latest arrival is the delivery time.
        This is a HARD constraint - must arrive exactly at delivery_time.

        Returns:
            Minutes from midnight
        """
        t = time.fromisoformat(self.delivery_time)
        return t.hour * 60 + t.minute

    @property
    def departure_time(self) -> int:
        """
        Get departure time from depot in minutes from midnight.
        Departure is 30 minutes before earliest delivery time.

        Returns:
            Minutes from midnight
        """
        return max(0, self.time_window_start - 30)

    def __repr__(self) -> str:
        """String representation of the order."""
        priority_flag = " [PRIORITY]" if self.is_priority else ""
        return (
            f"Order({self.sale_order_id}, {self.display_name}, "
            f"{self.load_weight_in_kg}kg, {self.delivery_time}{priority_flag})"
        )
