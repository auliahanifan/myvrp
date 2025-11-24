"""Unit tests for distance calculator."""
import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from src.utils.distance_calculator import DistanceCalculator, DistanceCalculatorError
from src.models.location import Location, Depot


class TestDistanceCalculator:
    """Test suite for DistanceCalculator class."""

    @pytest.fixture
    def sample_locations(self):
        """Create sample locations for testing."""
        depot = Depot("Depot", (-6.2088, 106.8456))
        loc1 = Location("Location 1", (-6.2100, 106.8500))
        loc2 = Location("Location 2", (-6.2200, 106.8600))
        return [depot, loc1, loc2]

    @pytest.fixture
    def mock_osrm_response_success(self):
        """Mock successful OSRM API response."""
        return {
            "code": "Ok",
            "distances": [
                [0, 5000, 10000],
                [5000, 0, 6000],
                [10000, 6000, 0]
            ],
            "durations": [
                [0, 600, 1200],
                [600, 0, 700],
                [1200, 700, 0]
            ]
        }

    def test_calculator_initialization(self):
        """Test distance calculator initialization."""
        calc = DistanceCalculator()
        assert calc.osrm_url == "https://osrm.segarloka.cc"
        assert calc.cache_dir == ".cache"

    @patch('src.utils.distance_calculator.requests.get')
    def test_calculate_matrix_success(self, mock_get, sample_locations, mock_osrm_response_success):
        """Test successful matrix calculation."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_osrm_response_success
        mock_get.return_value = mock_response

        calc = DistanceCalculator(cache_dir="/tmp/test_cache")
        dist_matrix, dur_matrix = calc.calculate_matrix(sample_locations)

        assert dist_matrix.shape == (3, 3)
        assert dur_matrix.shape == (3, 3)

        assert dist_matrix[0, 1] == 5.0  # 5000m = 5km
        assert dur_matrix[0, 1] == 10.0  # 600s = 10min

    def test_calculate_matrix_empty_locations(self):
        """Test that calculator raises error for empty locations."""
        calc = DistanceCalculator()

        with pytest.raises(DistanceCalculatorError) as exc_info:
            calc.calculate_matrix([])
        assert "Location list cannot be empty" in str(exc_info.value)

    @patch('src.utils.distance_calculator.requests.get')
    def test_calculate_matrix_api_error(self, mock_get, sample_locations):
        """Test handling of API errors."""
        mock_get.side_effect = requests.exceptions.RequestException("API Error")

        calc = DistanceCalculator(cache_dir="/tmp/test_cache")
        dist_matrix, dur_matrix = calc.calculate_matrix(sample_locations)
        
        assert calc.haversine_fallbacks == 1
        assert np.all(dist_matrix >= 0)
        assert np.all(dur_matrix >= 0)

    @patch('src.utils.distance_calculator.requests.get')
    def test_calculate_matrix_status_not_ok(self, mock_get, sample_locations):
        """Test handling of non-OK status from API."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response

        calc = DistanceCalculator(cache_dir="/tmp/test_cache")
        dist_matrix, dur_matrix = calc.calculate_matrix(sample_locations)

        assert calc.haversine_fallbacks == 1
        assert np.all(dist_matrix >= 0)
        assert np.all(dur_matrix >= 0)

    @patch('src.utils.distance_calculator.requests.get')
    def test_calculate_matrix_code_not_ok(self, mock_get, sample_locations):
        """Test handling of error code from API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"code": "InvalidQuery", "message": "Invalid query"}
        mock_get.return_value = mock_response

        calc = DistanceCalculator(cache_dir="/tmp/test_cache")
        dist_matrix, dur_matrix = calc.calculate_matrix(sample_locations)

        assert calc.haversine_fallbacks == 1
        assert np.all(dist_matrix >= 0)
        assert np.all(dur_matrix >= 0)

    @patch('src.utils.distance_calculator.requests.get')
    def test_caching_mechanism(self, mock_get, sample_locations, mock_osrm_response_success):
        """Test that caching works correctly."""
        import tempfile
        import shutil

        temp_cache = tempfile.mkdtemp()

        try:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_osrm_response_success
            mock_get.return_value = mock_response

            calc = DistanceCalculator(cache_dir=temp_cache)

            # First call - should hit API
            dist_matrix1, dur_matrix1 = calc.calculate_matrix(sample_locations)
            assert mock_get.call_count == 1

            # Second call - should use cache
            dist_matrix2, dur_matrix2 = calc.calculate_matrix(sample_locations)
            assert mock_get.call_count == 1  # Still 1, no new API call

            np.testing.assert_array_equal(dist_matrix1, dist_matrix2)
            np.testing.assert_array_equal(dur_matrix1, dur_matrix2)

        finally:
            shutil.rmtree(temp_cache)

    def test_cache_key_generation(self, sample_locations):
        """Test that cache key is generated consistently."""
        calc = DistanceCalculator()

        key1 = calc._generate_cache_key(sample_locations)
        key2 = calc._generate_cache_key(sample_locations)

        assert key1 == key2
        assert len(key1) == 32  # MD5 hash length

    @patch('src.utils.distance_calculator.requests.get')
    def test_clear_cache(self, mock_get, sample_locations, mock_osrm_response_success):
        """Test cache clearing functionality."""
        import tempfile
        import shutil

        temp_cache = tempfile.mkdtemp()

        try:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_osrm_response_success
            mock_get.return_value = mock_response

            calc = DistanceCalculator(cache_dir=temp_cache)

            calc.calculate_matrix(sample_locations)
            assert calc.get_cache_size() > 0

            calc.clear_cache()
            assert calc.get_cache_size() == 0

        finally:
            shutil.rmtree(temp_cache)

    @patch('src.utils.distance_calculator.requests.get')
    def test_api_call_format(self, mock_get, sample_locations):
        """Test that API is called with correct format."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "code": "Ok",
            "distances": [[0]],
            "durations": [[0]]
        }
        mock_get.return_value = mock_response

        calc = DistanceCalculator(cache_dir="/tmp/test_cache")
        calc.calculate_matrix(sample_locations)

        assert mock_get.called
        call_args = mock_get.call_args

        coords_str = ";".join(f"{loc.longitude},{loc.latitude}" for loc in sample_locations)
        expected_url = f"http://osrm.segarloka.cc/table/v1/car/{coords_str}"
        assert call_args[0][0] == expected_url

        params = call_args[1]["params"]
        assert params["annotations"] == "duration,distance"

    def test_haversine_distance(self):
        """Test Haversine distance calculation."""
        calc = DistanceCalculator()

        jakarta = (-6.2088, 106.8456)
        bandung = (-6.9175, 107.6191)

        distance = calc._haversine_distance(jakarta, bandung)

        assert 140 <= distance <= 160
