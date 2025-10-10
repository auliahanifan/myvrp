"""
Distance calculator using Radar Distance Matrix API.
Calculates distance and duration matrices with caching support.
"""
import requests
import pickle
import hashlib
import os
import time
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Optional
import numpy as np
from ..models.location import Location


class DistanceCalculatorError(Exception):
    """Custom exception for distance calculator errors."""
    pass


class DistanceCalculator:
    """
    Calculator for distance and duration matrices using Radar API.
    Implements caching to minimize API calls and costs.
    """

    def __init__(
        self,
        api_key: str,
        cache_dir: str = ".cache",
        cache_ttl_hours: int = 24,
        enable_cache: bool = True
    ):
        """
        Initialize distance calculator.

        Args:
            api_key: Radar API key
            cache_dir: Directory for caching API responses
            cache_ttl_hours: Cache time-to-live in hours (default: 24)
            enable_cache: Enable/disable caching (default: True)
        """
        if not api_key:
            raise DistanceCalculatorError("Radar API key is required")

        self.api_key = api_key
        self.cache_dir = cache_dir
        self.base_url = "https://api.radar.io/v1"
        self.cache_ttl_hours = cache_ttl_hours
        self.enable_cache = enable_cache

        # Cache statistics
        self.cache_hits = 0
        self.cache_misses = 0
        self.api_calls = 0

        # Create cache directory if it doesn't exist
        if enable_cache:
            os.makedirs(cache_dir, exist_ok=True)

    def calculate_matrix(
        self, locations: List[Location], force_refresh: bool = False
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate distance and duration matrices for all locations.

        Args:
            locations: List of Location objects (depot + customers)
            force_refresh: Force API call even if cache exists

        Returns:
            Tuple of (distance_matrix, duration_matrix)
            - distance_matrix: 2D array of distances in kilometers
            - duration_matrix: 2D array of durations in minutes

        Raises:
            DistanceCalculatorError: If API call fails
        """
        if not locations:
            raise DistanceCalculatorError("Location list cannot be empty")

        # Check cache first (if enabled and not forcing refresh)
        cache_key = self._generate_cache_key(locations)
        if self.enable_cache and not force_refresh:
            cached_result = self._load_from_cache(cache_key)
            if cached_result is not None:
                self.cache_hits += 1
                return cached_result
            self.cache_misses += 1

        # Extract coordinates
        coordinates = [loc.to_tuple() for loc in locations]
        n = len(coordinates)

        # Initialize matrices
        distance_matrix = np.zeros((n, n))
        duration_matrix = np.zeros((n, n))

        # Radar API supports multiple origins and destinations in a single request
        # Format: origins=lat1,lng1|lat2,lng2&destinations=lat3,lng3|lat4,lng4
        # Using batches to avoid hitting URL length limits (typically ~2000 chars)
        batch_size = 200  # Conservative batch size for URL length

        try:
            for i in range(0, n, batch_size):
                origins_batch = coordinates[i : min(i + batch_size, n)]

                for j in range(0, n, batch_size):
                    destinations_batch = coordinates[j : min(j + batch_size, n)]

                    # Call Radar Distance Matrix API
                    self.api_calls += 1
                    result = self._call_radar_matrix_api(
                        origins_batch, destinations_batch
                    )

                    # Parse results
                    self._parse_api_response(
                        result,
                        distance_matrix,
                        duration_matrix,
                        i,
                        j,
                    )

        except requests.exceptions.RequestException as e:
            raise DistanceCalculatorError(f"Radar API request error: {str(e)}")
        except Exception as e:
            raise DistanceCalculatorError(f"Error calling Radar API: {str(e)}")

        # Cache the result with metadata
        if self.enable_cache:
            self._save_to_cache(cache_key, (distance_matrix, duration_matrix))

        return distance_matrix, duration_matrix

    def _call_radar_matrix_api(
        self, origins: List[Tuple[float, float]], destinations: List[Tuple[float, float]]
    ) -> dict:
        """
        Call Radar Distance Matrix API.

        Args:
            origins: List of (latitude, longitude) tuples
            destinations: List of (latitude, longitude) tuples

        Returns:
            API response as dictionary

        Raises:
            DistanceCalculatorError: If API call fails
        """
        # Format coordinates: "lat,lng|lat,lng|..."
        origins_str = "|".join(f"{lat},{lng}" for lat, lng in origins)
        destinations_str = "|".join(f"{lat},{lng}" for lat, lng in destinations)

        url = f"{self.base_url}/route/matrix"
        params = {
            "origins": origins_str,
            "destinations": destinations_str,
            "mode": "car",
            "units": "metric",
        }
        headers = {"Authorization": self.api_key}

        response = requests.get(url, params=params, headers=headers, timeout=30)

        if response.status_code != 200:
            raise DistanceCalculatorError(
                f"Radar API returned status {response.status_code}: {response.text}"
            )

        data = response.json()

        if data.get("meta", {}).get("code") != 200:
            raise DistanceCalculatorError(
                f"Radar API error: {data.get('meta', {})}"
            )

        return data

    def _parse_api_response(
        self,
        response: dict,
        distance_matrix: np.ndarray,
        duration_matrix: np.ndarray,
        row_offset: int,
        col_offset: int,
    ):
        """
        Parse Radar API response and fill matrices.

        Args:
            response: API response dictionary
            distance_matrix: Distance matrix to fill
            duration_matrix: Duration matrix to fill
            row_offset: Row offset for batch processing
            col_offset: Column offset for batch processing

        Raises:
            DistanceCalculatorError: If response is invalid
        """
        matrix = response.get("matrix", [])

        if not matrix:
            raise DistanceCalculatorError("Empty matrix in API response")

        # Radar returns matrix as a 2D array: matrix[origin_index][destination_index]
        for origin_idx, row in enumerate(matrix):
            for route in row:
                dest_idx = route.get("destinationIndex")

                if dest_idx is None:
                    continue

                # Check if route was found
                distance_data = route.get("distance", {})
                duration_data = route.get("duration", {})

                if distance_data and duration_data:
                    # Distance in kilometers (Radar returns meters)
                    distance_m = distance_data.get("value", 0)
                    distance_km = distance_m / 1000.0

                    # Duration in minutes (Radar returns minutes as float)
                    duration_min = duration_data.get("value", 0)

                    distance_matrix[row_offset + origin_idx, col_offset + dest_idx] = distance_km
                    duration_matrix[row_offset + origin_idx, col_offset + dest_idx] = duration_min
                else:
                    # If route not found, use large penalty value
                    distance_matrix[row_offset + origin_idx, col_offset + dest_idx] = 999999
                    duration_matrix[row_offset + origin_idx, col_offset + dest_idx] = 999999

    def _generate_cache_key(self, locations: List[Location]) -> str:
        """
        Generate a unique cache key for a set of locations.

        Args:
            locations: List of locations

        Returns:
            Cache key string
        """
        # Create a string representation of all coordinates
        coord_str = ";".join(
            f"{loc.latitude:.6f},{loc.longitude:.6f}" for loc in locations
        )

        # Hash the string to create a cache key
        return hashlib.md5(coord_str.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> str:
        """
        Get the file path for a cache key.

        Args:
            cache_key: Cache key

        Returns:
            Full path to cache file
        """
        return os.path.join(self.cache_dir, f"distance_matrix_{cache_key}.pkl")

    def _load_from_cache(
        self, cache_key: str
    ) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Load distance and duration matrices from cache with TTL check.

        Args:
            cache_key: Cache key

        Returns:
            Tuple of (distance_matrix, duration_matrix) or None if not cached/expired
        """
        cache_path = self._get_cache_path(cache_key)

        if not os.path.exists(cache_path):
            return None

        try:
            # Check if cache is expired
            file_age = time.time() - os.path.getmtime(cache_path)
            cache_ttl_seconds = self.cache_ttl_hours * 3600

            if file_age > cache_ttl_seconds:
                # Cache expired, delete it
                os.remove(cache_path)
                return None

            with open(cache_path, "rb") as f:
                cached_data = pickle.load(f)

            # Support both old format (tuple) and new format (dict with metadata)
            if isinstance(cached_data, dict):
                return (cached_data["distance_matrix"], cached_data["duration_matrix"])
            else:
                # Old format, just return the tuple
                return cached_data

        except Exception:
            # If cache is corrupted, delete it and return None
            try:
                os.remove(cache_path)
            except:
                pass
            return None

    def _save_to_cache(
        self, cache_key: str, data: Tuple[np.ndarray, np.ndarray]
    ):
        """
        Save distance and duration matrices to cache with metadata.

        Args:
            cache_key: Cache key
            data: Tuple of (distance_matrix, duration_matrix)
        """
        cache_path = self._get_cache_path(cache_key)

        try:
            # Save with metadata
            cache_data = {
                "distance_matrix": data[0],
                "duration_matrix": data[1],
                "cached_at": datetime.now().isoformat(),
                "ttl_hours": self.cache_ttl_hours,
            }
            with open(cache_path, "wb") as f:
                pickle.dump(cache_data, f)
        except Exception:
            # If caching fails, just continue without caching
            pass

    def clear_cache(self):
        """Clear all cached distance matrices."""
        if os.path.exists(self.cache_dir):
            for filename in os.listdir(self.cache_dir):
                if filename.startswith("distance_matrix_"):
                    os.remove(os.path.join(self.cache_dir, filename))

    def get_cache_size(self) -> int:
        """
        Get the number of cached distance matrices.

        Returns:
            Number of cached files
        """
        if not os.path.exists(self.cache_dir):
            return 0

        return len(
            [
                f
                for f in os.listdir(self.cache_dir)
                if f.startswith("distance_matrix_")
            ]
        )

    def get_cache_stats(self) -> Dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "total_requests": total_requests,
            "hit_rate_percent": round(hit_rate, 2),
            "api_calls": self.api_calls,
            "cached_files": self.get_cache_size(),
            "cache_enabled": self.enable_cache,
            "cache_ttl_hours": self.cache_ttl_hours,
        }

    def clear_expired_cache(self) -> int:
        """
        Clear only expired cache files.

        Returns:
            Number of files deleted
        """
        if not os.path.exists(self.cache_dir):
            return 0

        deleted_count = 0
        cache_ttl_seconds = self.cache_ttl_hours * 3600

        for filename in os.listdir(self.cache_dir):
            if filename.startswith("distance_matrix_"):
                filepath = os.path.join(self.cache_dir, filename)
                file_age = time.time() - os.path.getmtime(filepath)

                if file_age > cache_ttl_seconds:
                    try:
                        os.remove(filepath)
                        deleted_count += 1
                    except:
                        pass

        return deleted_count
