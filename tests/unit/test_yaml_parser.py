"""Unit tests for YAML parser."""
import pytest
import tempfile
import os
from src.utils.yaml_parser import YAMLParser, YAMLParserError
from src.models.vehicle import Vehicle, VehicleFleet


class TestYAMLParser:
    """Test suite for YAMLParser class."""

    @pytest.fixture
    def valid_yaml_data(self):
        """Create valid YAML data for testing."""
        return """vehicles:
  - name: "L300"
    capacity: 800
    cost_per_km: 5000

  - name: "Granmax"
    capacity: 500
    cost_per_km: 3500

  - name: "Pickup Small"
    capacity: 300
    cost_per_km: 2500

unlimited: true
"""

    @pytest.fixture
    def valid_yaml_file(self, valid_yaml_data):
        """Create temporary YAML file with valid data."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as f:
            f.write(valid_yaml_data)
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    @pytest.fixture
    def invalid_yaml_missing_vehicles(self):
        """YAML missing vehicles key."""
        data = """unlimited: true"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as f:
            f.write(data)
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    @pytest.fixture
    def invalid_yaml_negative_capacity(self):
        """YAML with negative capacity."""
        data = """vehicles:
  - name: "Bad Vehicle"
    capacity: -100
    cost_per_km: 5000
unlimited: true"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as f:
            f.write(data)
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    @pytest.fixture
    def invalid_yaml_zero_cost(self):
        """YAML with zero cost per km."""
        data = """vehicles:
  - name: "Free Vehicle"
    capacity: 500
    cost_per_km: 0
unlimited: true"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as f:
            f.write(data)
            temp_path = f.name
        yield temp_path
        os.unlink(temp_path)

    def test_parse_valid_yaml(self, valid_yaml_file):
        """Test parsing valid YAML file."""
        parser = YAMLParser(valid_yaml_file)
        fleet = parser.parse()

        assert isinstance(fleet, VehicleFleet)
        assert fleet.unlimited is True
        assert len(fleet.vehicle_types) == 3

        # Check first vehicle
        l300 = fleet.vehicle_types[0]
        assert l300.name == "L300"
        assert l300.capacity == 800
        assert l300.cost_per_km == 5000

    def test_parse_missing_vehicles_key(self, invalid_yaml_missing_vehicles):
        """Test that parser raises error for missing vehicles key."""
        parser = YAMLParser(invalid_yaml_missing_vehicles)

        with pytest.raises(YAMLParserError) as exc_info:
            parser.parse()

        assert "Missing 'vehicles' key" in str(exc_info.value)

    def test_parse_negative_capacity(self, invalid_yaml_negative_capacity):
        """Test that parser catches negative capacity."""
        parser = YAMLParser(invalid_yaml_negative_capacity)

        with pytest.raises(YAMLParserError) as exc_info:
            parser.parse()

        assert "Capacity must be positive" in str(exc_info.value)

    def test_parse_zero_cost(self, invalid_yaml_zero_cost):
        """Test that parser catches zero cost."""
        parser = YAMLParser(invalid_yaml_zero_cost)

        with pytest.raises(YAMLParserError) as exc_info:
            parser.parse()

        assert "Cost per km must be positive" in str(exc_info.value)

    def test_parse_file_not_found(self):
        """Test that parser raises error for non-existent file."""
        parser = YAMLParser("nonexistent_file.yaml")

        with pytest.raises(YAMLParserError) as exc_info:
            parser.parse()

        assert "YAML file not found" in str(exc_info.value)

    def test_fleet_unlimited_flag(self, valid_yaml_file):
        """Test that unlimited flag is parsed correctly."""
        parser = YAMLParser(valid_yaml_file)
        fleet = parser.parse()

        assert fleet.unlimited is True

    def test_fleet_get_vehicle_by_index(self, valid_yaml_file):
        """Test getting vehicle by index (with unlimited fleet)."""
        parser = YAMLParser(valid_yaml_file)
        fleet = parser.parse()

        # Should be able to get vehicles beyond initial count
        vehicle_0 = fleet.get_vehicle_by_index(0)
        vehicle_10 = fleet.get_vehicle_by_index(10)

        assert vehicle_0.name == "L300"
        # Vehicle 10 should be cloned from vehicle types (10 % 3 = 1)
        assert vehicle_10.name == "Granmax"

    def test_empty_vehicles_list(self):
        """Test parsing YAML with empty vehicles list."""
        data = """vehicles: []
unlimited: true"""

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as f:
            f.write(data)
            temp_path = f.name

        try:
            parser = YAMLParser(temp_path)
            with pytest.raises(YAMLParserError) as exc_info:
                parser.parse()
            assert "At least one vehicle type required" in str(exc_info.value)
        finally:
            os.unlink(temp_path)

    def test_parse_limited_fleet(self):
        """Test parsing YAML with limited fleet."""
        data = """vehicles:
  - name: "Van"
    capacity: 600
    cost_per_km: 4000

unlimited: false"""

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as f:
            f.write(data)
            temp_path = f.name

        try:
            parser = YAMLParser(temp_path)
            fleet = parser.parse()
            assert fleet.unlimited is False
        finally:
            os.unlink(temp_path)
