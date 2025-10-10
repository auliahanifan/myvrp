"""Unit tests for CSV parser."""
import pytest
import pandas as pd
import tempfile
import os
from src.utils.csv_parser import CSVParser, CSVParserError
from src.models.order import Order


class TestCSVParser:
    """Test suite for CSVParser class."""

    @pytest.fixture
    def valid_csv_data(self):
        """Create valid CSV data for testing."""
        return """sale_order_id,delivery_date,delivery_time,load_weight_in_kg,partner_id,display_name,alamat,partner_latitude,partner_longitude,is_priority
ORDER001,2025-10-08,04:00-05:00,50.0,P001,Customer A,Address A,-6.2088,106.8456,false
ORDER002,2025-10-08,05:00-06:00,75.5,P002,Customer B,Address B,-6.2100,106.8500,true
ORDER003,2025-10-08T06:00:00,06:00-07:00,25.0,P003,Customer C,Address C,-6.2200,106.8600,false"""

    @pytest.fixture
    def valid_csv_file(self, valid_csv_data):
        """Create temporary CSV file with valid data."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            f.write(valid_csv_data)
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    @pytest.fixture
    def invalid_csv_missing_columns(self):
        """CSV missing required columns."""
        data = """sale_order_id,delivery_date
ORDER001,2025-10-08"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            f.write(data)
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    @pytest.fixture
    def invalid_csv_bad_coordinates(self):
        """CSV with invalid coordinates."""
        data = """sale_order_id,delivery_date,delivery_time,load_weight_in_kg,partner_id,display_name,alamat,partner_latitude,partner_longitude,is_priority
ORDER001,2025-10-08,04:00-05:00,50.0,P001,Customer A,Address A,999.0,106.8456,false"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            f.write(data)
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    @pytest.fixture
    def invalid_csv_negative_weight(self):
        """CSV with negative weight."""
        data = """sale_order_id,delivery_date,delivery_time,load_weight_in_kg,partner_id,display_name,alamat,partner_latitude,partner_longitude,is_priority
ORDER001,2025-10-08,04:00-05:00,-10.0,P001,Customer A,Address A,-6.2088,106.8456,false"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            f.write(data)
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    def test_parse_valid_csv(self, valid_csv_file):
        """Test parsing valid CSV file."""
        parser = CSVParser(valid_csv_file)
        orders = parser.parse()

        assert len(orders) == 3
        assert all(isinstance(order, Order) for order in orders)

        # Check first order
        assert orders[0].sale_order_id == "ORDER001"
        assert orders[0].delivery_time == "04:00-05:00"
        assert orders[0].load_weight_in_kg == 50.0
        assert orders[0].is_priority is False
        assert orders[0].coordinates == (-6.2088, 106.8456)

        # Check second order (priority)
        assert orders[1].is_priority is True

    def test_parse_missing_columns(self, invalid_csv_missing_columns):
        """Test that parser raises error for missing columns."""
        parser = CSVParser(invalid_csv_missing_columns)

        with pytest.raises(CSVParserError) as exc_info:
            parser.parse()

        assert "Missing required columns" in str(exc_info.value)

    def test_parse_invalid_coordinates(self, invalid_csv_bad_coordinates):
        """Test that parser catches invalid coordinates."""
        parser = CSVParser(invalid_csv_bad_coordinates)

        with pytest.raises(CSVParserError) as exc_info:
            parser.parse()

        assert "Invalid latitude" in str(exc_info.value)

    def test_parse_negative_weight(self, invalid_csv_negative_weight):
        """Test that parser catches negative weights."""
        parser = CSVParser(invalid_csv_negative_weight)

        with pytest.raises(CSVParserError) as exc_info:
            parser.parse()

        assert "Weight must be positive" in str(exc_info.value)

    def test_parse_file_not_found(self):
        """Test that parser raises error for non-existent file."""
        parser = CSVParser("nonexistent_file.csv")

        with pytest.raises(CSVParserError) as exc_info:
            parser.parse()

        assert "CSV file not found" in str(exc_info.value)

    def test_parse_time_range_format(self, valid_csv_file):
        """Test parsing time range format (HH:MM-HH:MM)."""
        parser = CSVParser(valid_csv_file)
        orders = parser.parse()

        # Check that time ranges are preserved
        assert "-" in orders[0].delivery_time
        assert orders[0].time_window_start == 240  # 04:00 = 4*60
        assert orders[0].time_window_end == 300    # 05:00 = 5*60

    def test_parse_iso_datetime_format(self, valid_csv_file):
        """Test parsing ISO datetime format in delivery_date."""
        parser = CSVParser(valid_csv_file)
        orders = parser.parse()

        # ORDER003 has ISO datetime format
        assert orders[2].delivery_date == "2025-10-08"

    def test_parse_priority_flag(self, valid_csv_file):
        """Test parsing priority flag."""
        parser = CSVParser(valid_csv_file)
        orders = parser.parse()

        assert orders[0].is_priority is False
        assert orders[1].is_priority is True
        assert orders[2].is_priority is False

    def test_parse_empty_csv(self):
        """Test parsing empty CSV file."""
        data = """sale_order_id,delivery_date,delivery_time,load_weight_in_kg,partner_id,display_name,alamat,partner_latitude,partner_longitude,is_priority"""

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            f.write(data)
            temp_path = f.name

        try:
            parser = CSVParser(temp_path)
            with pytest.raises(CSVParserError) as exc_info:
                parser.parse()
            assert "No valid orders" in str(exc_info.value)
        finally:
            os.unlink(temp_path)
