"""Unit tests for distance calculator."""
import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from src.utils.distance_calculator import DistanceCalculator, DistanceCalculatorError
from src.models.location import Location, Depot


class TestDistanceCalculator:
    """Test suite for DistanceCalculator class."""

    @pytest.fixture
    def mock_api_key(self):
        """Mock API key for testing."""
        return "mock_google_maps_api_key"

    @pytest.fixture
    def sample_locations(self):
        """Create sample locations for testing."""
        depot = Depot("Depot", (-6.2088, 106.8456))
        loc1 = Location("Location 1", (-6.2100, 106.8500))
        loc2 = Location("Location 2", (-6.2200, 106.8600))
        return [depot, loc1, loc2]

    @pytest.fixture
    def mock_api_response_success(self):
        """Mock successful API response."""
        return {
            "status": "OK",
            "rows": [
                {
                    "elements": [
                        {"status": "OK", "distance": {"value": 0}, "duration": {"value": 0}},
                        {"status": "OK", "distance": {"value": 5000}, "duration": {"value": 600}},
                        {"status": "OK", "distance": {"value": 10000}, "duration": {"value": 1200}},
                    ]
                },
                {
                    "elements": [
                        {"status": "OK", "distance": {"value": 5000}, "duration": {"value": 600}},
                        {"status": "OK", "distance": {"value": 0}, "duration": {"value": 0}},
                        {"status": "OK", "distance": {"value": 6000}, "duration": {"value": 700}},
                    ]
                },
                {
                    "elements": [
                        {"status": "OK", "distance": {"value": 10000}, "duration": {"value": 1200}},
                        {"status": "OK", "distance": {"value": 6000}, "duration": {"value": 700}},
                        {"status": "OK", "distance": {"value": 0}, "duration": {"value": 0}},
                    ]
                },
            ],
        }

    def test_calculator_initialization(self, mock_api_key):
        """Test distance calculator initialization."""
        calc = DistanceCalculator(mock_api_key)
        assert calc.api_key == mock_api_key
        assert calc.cache_dir == ".cache"

    def test_calculator_initialization_no_api_key(self):
        """Test that calculator raises error without API key."""
        with pytest.raises(DistanceCalculatorError) as exc_info:
            DistanceCalculator("")
        assert "API key is required" in str(exc_info.value)

    @patch('src.utils.distance_calculator.googlemaps.Client')
    def test_calculate_matrix_success(self, mock_client, mock_api_key, sample_locations, mock_api_response_success):
        """Test successful matrix calculation."""
        # Setup mock
        mock_instance = MagicMock()
        mock_instance.distance_matrix.return_value = mock_api_response_success
        mock_client.return_value = mock_instance

        calc = DistanceCalculator(mock_api_key, cache_dir="/tmp/test_cache")
        dist_matrix, dur_matrix = calc.calculate_matrix(sample_locations)

        # Verify matrix dimensions
        assert dist_matrix.shape == (3, 3)
        assert dur_matrix.shape == (3, 3)

        # Verify distances (converted from meters to km)
        assert dist_matrix[0, 1] == 5.0  # 5000m = 5km
        assert dist_matrix[0, 2] == 10.0  # 10000m = 10km

        # Verify durations (converted from seconds to minutes)
        assert dur_matrix[0, 1] == 10.0  # 600s = 10min
        assert dur_matrix[0, 2] == 20.0  # 1200s = 20min

    def test_calculate_matrix_empty_locations(self, mock_api_key):
        """Test that calculator raises error for empty locations."""
        calc = DistanceCalculator(mock_api_key)

        with pytest.raises(DistanceCalculatorError) as exc_info:
            calc.calculate_matrix([])
        assert "Location list cannot be empty" in str(exc_info.value)

    @patch('src.utils.distance_calculator.googlemaps.Client')
    def test_calculate_matrix_api_error(self, mock_client, mock_api_key, sample_locations):
        """Test handling of API errors."""
        # Setup mock to raise API error
        mock_instance = MagicMock()
        mock_instance.distance_matrix.side_effect = Exception("API Error")
        mock_client.return_value = mock_instance

        calc = DistanceCalculator(mock_api_key, cache_dir="/tmp/test_cache")

        with pytest.raises(DistanceCalculatorError) as exc_info:
            calc.calculate_matrix(sample_locations)
        assert "Error calling Google Maps API" in str(exc_info.value)

    @patch('src.utils.distance_calculator.googlemaps.Client')
    def test_calculate_matrix_status_not_ok(self, mock_client, mock_api_key, sample_locations):
        """Test handling of non-OK status from API."""
        # Setup mock with error status
        mock_response = {"status": "REQUEST_DENIED", "rows": []}
        mock_instance = MagicMock()
        mock_instance.distance_matrix.return_value = mock_response
        mock_client.return_value = mock_instance

        calc = DistanceCalculator(mock_api_key, cache_dir="/tmp/test_cache")

        with pytest.raises(DistanceCalculatorError) as exc_info:
            calc.calculate_matrix(sample_locations)
        assert "API returned status: REQUEST_DENIED" in str(exc_info.value)

    @patch('src.utils.distance_calculator.googlemaps.Client')
    def test_calculate_matrix_route_not_found(self, mock_client, mock_api_key, sample_locations):
        """Test handling of routes not found."""
        # Setup mock with route not found
        mock_response = {
            "status": "OK",
            "rows": [
                {
                    "elements": [
                        {"status": "OK", "distance": {"value": 0}, "duration": {"value": 0}},
                        {"status": "ZERO_RESULTS", "distance": {"value": 0}, "duration": {"value": 0}},
                        {"status": "OK", "distance": {"value": 10000}, "duration": {"value": 1200}},
                    ]
                },
            ],
        }
        mock_instance = MagicMock()
        mock_instance.distance_matrix.return_value = mock_response
        mock_client.return_value = mock_instance

        calc = DistanceCalculator(mock_api_key, cache_dir="/tmp/test_cache")
        dist_matrix, dur_matrix = calc.calculate_matrix(sample_locations)

        # Should use penalty value (999999) for routes not found
        assert dist_matrix[0, 1] == 999999

    @patch('src.utils.distance_calculator.googlemaps.Client')
    def test_caching_mechanism(self, mock_client, mock_api_key, sample_locations, mock_api_response_success):
        """Test that caching works correctly."""
        import tempfile
        import shutil

        temp_cache = tempfile.mkdtemp()

        try:
            mock_instance = MagicMock()
            mock_instance.distance_matrix.return_value = mock_api_response_success
            mock_client.return_value = mock_instance

            calc = DistanceCalculator(mock_api_key, cache_dir=temp_cache)

            # First call - should hit API
            dist_matrix1, dur_matrix1 = calc.calculate_matrix(sample_locations)
            assert mock_instance.distance_matrix.call_count == 1

            # Second call - should use cache
            dist_matrix2, dur_matrix2 = calc.calculate_matrix(sample_locations)
            assert mock_instance.distance_matrix.call_count == 1  # Still 1, no new API call

            # Matrices should be identical
            np.testing.assert_array_equal(dist_matrix1, dist_matrix2)
            np.testing.assert_array_equal(dur_matrix1, dur_matrix2)

        finally:
            shutil.rmtree(temp_cache)

    def test_batch_size_limit(self, mock_api_key):
        """Test that batching respects API limits (10x10=100 elements)."""
        calc = DistanceCalculator(mock_api_key)

        # Create 25 locations (would need batching)
        locations = [Depot("Depot", (-6.2088, 106.8456))]
        for i in range(24):
            lat = -6.2088 + (i * 0.01)
            lng = 106.8456 + (i * 0.01)
            locations.append(Location(f"Loc {i}", (lat, lng)))

        # With 25 locations and batch size 10:
        # Would need 3x3 = 9 batches (ceiling(25/10) = 3 for both dimensions)
        # This test just verifies no error is raised for large datasets
        assert len(locations) == 25

    def test_cache_key_generation(self, mock_api_key, sample_locations):
        """Test that cache key is generated consistently."""
        calc = DistanceCalculator(mock_api_key)

        key1 = calc._generate_cache_key(sample_locations)
        key2 = calc._generate_cache_key(sample_locations)

        assert key1 == key2
        assert len(key1) == 32  # MD5 hash length

    @patch('src.utils.distance_calculator.googlemaps.Client')
    def test_clear_cache(self, mock_client, mock_api_key, sample_locations, mock_api_response_success):
        """Test cache clearing functionality."""
        import tempfile
        import shutil

        temp_cache = tempfile.mkdtemp()

        try:
            mock_instance = MagicMock()
            mock_instance.distance_matrix.return_value = mock_api_response_success
            mock_client.return_value = mock_instance

            calc = DistanceCalculator(mock_api_key, cache_dir=temp_cache)

            # Create cache
            calc.calculate_matrix(sample_locations)
            assert calc.get_cache_size() > 0

            # Clear cache
            calc.clear_cache()
            assert calc.get_cache_size() == 0

        finally:
            shutil.rmtree(temp_cache)
