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
    kota: Optional[str] = None
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

        # Normalize and validate delivery_date format (accept both YYYY-MM-DD and ISO datetime)
        self.delivery_date = self._normalize_date(self.delivery_date)

        # Validate delivery_time format (supports HH:MM or HH:MM-HH:MM)
        self._validate_time_format(self.delivery_time)

    def _validate_time_format(self, time_str: str):
        """
        Validate time format. Accepts HH:MM or HH:MM-HH:MM formats.

        Args:
            time_str: Time string to validate

        Raises:
            ValueError: If time format is invalid
        """
        try:
            # Handle time range format (e.g., "04:00-05:00")
            if '-' in time_str:
                parts = time_str.split('-')
                if len(parts) != 2:
                    raise ValueError("Time range must have exactly one '-'")
                time.fromisoformat(parts[0])  # Validate start time
                time.fromisoformat(parts[1])  # Validate end time
            # Handle single time format (e.g., "04:00")
            else:
                time.fromisoformat(time_str)
        except ValueError:
            raise ValueError(
                f"Order {self.sale_order_id}: Invalid time format '{time_str}'. "
                "Expected HH:MM or HH:MM-HH:MM"
            )

    def _normalize_date(self, date_str: str) -> str:
        """
        Normalize date string to YYYY-MM-DD format.
        Accepts both YYYY-MM-DD and ISO datetime formats (YYYY-MM-DDTHH:MM:SS).

        Args:
            date_str: Date string in various formats

        Returns:
            Normalized date string in YYYY-MM-DD format

        Raises:
            ValueError: If date format is invalid
        """
        try:
            # Try ISO datetime format first (YYYY-MM-DDTHH:MM:SS)
            if 'T' in date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return dt.strftime("%Y-%m-%d")
            # Try simple date format (YYYY-MM-DD)
            else:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                return date_str
        except ValueError:
            raise ValueError(
                f"Order {self.sale_order_id}: Invalid date format '{date_str}'. "
                "Expected YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"
            )

    @property
    def time_window_start(self) -> int:
        """
        Get time window start in minutes from midnight.
        Supports both single time (HH:MM) and time range (HH:MM-HH:MM) formats.

        Returns:
            Minutes from midnight (earliest acceptable arrival)
        """
        # Handle time range format (e.g., "04:00-05:00")
        if '-' in self.delivery_time:
            start_time_str = self.delivery_time.split('-')[0]
            t = time.fromisoformat(start_time_str)
            return t.hour * 60 + t.minute
        # Handle single time format (e.g., "04:00")
        else:
            t = time.fromisoformat(self.delivery_time)
            return t.hour * 60 + t.minute

    @property
    def time_window_end(self) -> int:
        """
        Get time window end in minutes from midnight.
        Supports both single time (HH:MM) and time range (HH:MM-HH:MM) formats.
        For single time, end = start (exact delivery time).
        For time range, end is the second time.

        Returns:
            Minutes from midnight (latest acceptable arrival)
        """
        # Handle time range format (e.g., "04:00-05:00")
        if '-' in self.delivery_time:
            end_time_str = self.delivery_time.split('-')[1]
            t = time.fromisoformat(end_time_str)
            return t.hour * 60 + t.minute
        # Handle single time format (e.g., "04:00")
        else:
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
            f"Order({self.sale_order_id}, {self.display_name}, {self.kota}, "
            f"{self.load_weight_in_kg}kg, {self.delivery_time}{priority_flag})"
        )
