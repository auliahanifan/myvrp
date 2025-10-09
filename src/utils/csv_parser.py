"""
CSV parser for order data.
Parses order CSV files and creates Order objects with validation.
"""
import pandas as pd
from typing import List, Tuple
from ..models.order import Order


class CSVParserError(Exception):
    """Custom exception for CSV parsing errors."""
    pass


class CSVParser:
    """
    Parser for order CSV files.

    Expected columns:
    - sale_order_id: Unique order identifier
    - delivery_date: Date of delivery (YYYY-MM-DD)
    - delivery_time: Time of delivery (HH:MM)
    - load_weight_in_kg: Weight in kilograms
    - partner_id: Customer partner ID
    - display_name: Customer display name
    - alamat: Full address
    - coordinates: Coordinates in "lat,lng" format
    - is_priority: Priority flag (optional, 0/1 or True/False)
    """

    REQUIRED_COLUMNS = [
        "sale_order_id",
        "delivery_date",
        "delivery_time",
        "load_weight_in_kg",
        "partner_id",
        "display_name",
        "alamat",
        "coordinates",
    ]

    def __init__(self, csv_path: str):
        """
        Initialize CSV parser.

        Args:
            csv_path: Path to CSV file
        """
        self.csv_path = csv_path
        self.df = None
        self.errors = []

    def parse(self) -> List[Order]:
        """
        Parse CSV file and return list of Order objects.

        Returns:
            List of Order objects

        Raises:
            CSVParserError: If parsing fails or validation errors occur
        """
        try:
            # Read CSV file
            self.df = pd.read_csv(self.csv_path)
        except FileNotFoundError:
            raise CSVParserError(f"CSV file not found: {self.csv_path}")
        except Exception as e:
            raise CSVParserError(f"Error reading CSV file: {str(e)}")

        # Validate columns
        self._validate_columns()

        # Parse orders
        orders = []
        for idx, row in self.df.iterrows():
            try:
                order = self._parse_row(row, idx)
                orders.append(order)
            except Exception as e:
                self.errors.append(f"Row {idx + 2}: {str(e)}")

        # Check for errors
        if self.errors:
            error_msg = "\n".join(self.errors)
            raise CSVParserError(f"Validation errors:\n{error_msg}")

        if not orders:
            raise CSVParserError("No valid orders found in CSV file")

        return orders

    def _validate_columns(self):
        """
        Validate that all required columns are present.

        Raises:
            CSVParserError: If required columns are missing
        """
        missing_columns = set(self.REQUIRED_COLUMNS) - set(self.df.columns)
        if missing_columns:
            raise CSVParserError(
                f"Missing required columns: {', '.join(missing_columns)}"
            )

    def _parse_row(self, row: pd.Series, idx: int) -> Order:
        """
        Parse a single row into an Order object.

        Args:
            row: DataFrame row
            idx: Row index (for error messages)

        Returns:
            Order object

        Raises:
            ValueError: If row data is invalid
        """
        # Check for missing required fields
        for col in self.REQUIRED_COLUMNS:
            if pd.isna(row[col]) or str(row[col]).strip() == "":
                raise ValueError(f"Missing required field: {col}")

        # Parse coordinates
        coordinates = self._parse_coordinates(row["coordinates"], idx)

        # Parse priority flag (optional)
        is_priority = False
        if "is_priority" in row and not pd.isna(row["is_priority"]):
            is_priority = self._parse_boolean(row["is_priority"])

        # Create Order object (validation happens in __post_init__)
        order = Order(
            sale_order_id=str(row["sale_order_id"]).strip(),
            delivery_date=str(row["delivery_date"]).strip(),
            delivery_time=str(row["delivery_time"]).strip(),
            load_weight_in_kg=float(row["load_weight_in_kg"]),
            partner_id=str(row["partner_id"]).strip(),
            display_name=str(row["display_name"]).strip(),
            alamat=str(row["alamat"]).strip(),
            coordinates=coordinates,
            is_priority=is_priority,
        )

        return order

    def _parse_coordinates(self, coord_str: str, idx: int) -> Tuple[float, float]:
        """
        Parse coordinates from string format "lat,lng".

        Args:
            coord_str: Coordinates string
            idx: Row index (for error messages)

        Returns:
            Tuple of (latitude, longitude)

        Raises:
            ValueError: If coordinates format is invalid
        """
        try:
            coord_str = str(coord_str).strip()
            parts = coord_str.split(",")
            if len(parts) != 2:
                raise ValueError(
                    f"Invalid coordinates format. Expected 'lat,lng', got: {coord_str}"
                )

            lat = float(parts[0].strip())
            lng = float(parts[1].strip())
            return (lat, lng)
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid coordinates: {coord_str}")

    def _parse_boolean(self, value) -> bool:
        """
        Parse boolean value from various formats.

        Args:
            value: Boolean value (can be 0/1, True/False, "true"/"false", etc.)

        Returns:
            Boolean value
        """
        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            return bool(value)

        if isinstance(value, str):
            value = value.strip().lower()
            return value in ("true", "1", "yes", "y")

        return False

    def get_summary(self) -> dict:
        """
        Get summary statistics of parsed data.

        Returns:
            Dictionary with summary stats
        """
        if self.df is None:
            return {}

        return {
            "total_rows": len(self.df),
            "unique_orders": self.df["sale_order_id"].nunique(),
            "unique_customers": self.df["partner_id"].nunique(),
            "total_weight": self.df["load_weight_in_kg"].sum(),
            "date_range": (
                self.df["delivery_date"].min(),
                self.df["delivery_date"].max(),
            ),
        }
