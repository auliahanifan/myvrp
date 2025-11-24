"""
Distance calculator using OSRM API.
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
from math import radians, cos, sin, asin, sqrt
from ..models.location import Location


class DistanceCalculatorError(Exception):
    """Custom exception for distance calculator errors."""
    pass


class DistanceCalculator:
    """
    Calculator for distance and duration matrices using OSRM API.
    Implements caching to minimize API calls.
    """

    def __init__(
        self,
        cache_dir: str = ".cache",
        cache_ttl_hours: int = 24,
        enable_cache: bool = True,
        fallback_speed_kmh: float = 40.0
    ):
        """
        Initialize distance calculator.

        Args:
            cache_dir: Directory for caching API responses
            cache_ttl_hours: Cache time-to-live in hours (default: 24)
            enable_cache: Enable/disable caching (default: True)
            fallback_speed_kmh: Assumed speed for duration estimation with Haversine (default: 40 km/h)
        """
        self.osrm_url = "https://osrm.segarloka.cc"
        self.cache_dir = cache_dir
        self.cache_ttl_hours = cache_ttl_hours
        self.enable_cache = enable_cache
        self.fallback_speed_kmh = fallback_speed_kmh

        # Cache statistics
        self.cache_hits = 0
        self.cache_misses = 0
        self.api_calls = 0
        self.haversine_fallbacks = 0

        # Create cache directory if it doesn't exist
        if enable_cache:
            os.makedirs(cache_dir, exist_ok=True)

    def _haversine_distance(self, coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
        """
        Calculate the great circle distance between two points on Earth using Haversine formula.

        Args:
            coord1: (latitude, longitude) tuple for first point
            coord2: (latitude, longitude) tuple for second point

        Returns:
            Distance in kilometers
        """
        lat1, lon1 = radians(coord1[0]), radians(coord1[1])
        lat2, lon2 = radians(coord2[0]), radians(coord2[1])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))

        # Radius of Earth in kilometers
        r = 6371

        return c * r

    def calculate_matrix(
        self, locations: List[Location], force_refresh: bool = False
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate distance and duration matrices for all locations.
        Uses OSRM API and falls back to Haversine formula for very distant pairs or API errors.

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

        try:
            self.api_calls += 1
            result = self._call_osrm_matrix_api(coordinates)
            self._parse_osrm_response(
                result,
                distance_matrix,
                duration_matrix,
            )
        except (DistanceCalculatorError, requests.exceptions.RequestException) as e:
            self.haversine_fallbacks += 1
            self._fill_matrix_haversine_full(coordinates, distance_matrix, duration_matrix)

        # Cache the result with metadata
        if self.enable_cache:
            self._save_to_cache(cache_key, (distance_matrix, duration_matrix))

        return distance_matrix, duration_matrix

    def _fill_matrix_haversine_full(
        self, 
        coordinates: List[Tuple[float, float]], 
        distance_matrix: np.ndarray, 
        duration_matrix: np.ndarray
    ):
        """Fill the entire matrix using Haversine distance calculation."""
        n = len(coordinates)
        for i in range(n):
            for j in range(n):
                distance_km = self._haversine_distance(coordinates[i], coordinates[j])
                duration_min = (distance_km / self.fallback_speed_kmh) * 60
                distance_matrix[i, j] = distance_km
                duration_matrix[i, j] = duration_min

    def _call_osrm_matrix_api(self, coordinates: List[Tuple[float, float]]) -> dict:
        """
        Call OSRM Table Service API.

        Args:
            coordinates: List of (latitude, longitude) tuples

        Returns:
            API response as dictionary

        Raises:
            DistanceCalculatorError: If API call fails
        """
        coords_str = ";".join(f"{lng},{lat}" for lat, lng in coordinates)
        url = f"{self.osrm_url}/table/v1/car/{coords_str}"
        params = {
            "annotations": "duration,distance"
        }

        response = requests.get(url, params=params, timeout=30)

        if response.status_code != 200:
            raise DistanceCalculatorError(
                f"OSRM API returned status {response.status_code}: {response.text}"
            )

        data = response.json()

        if data.get("code") != "Ok":
            raise DistanceCalculatorError(
                f"OSRM API error: {data.get('message', 'Unknown error')}"
            )

        return data

    def _parse_osrm_response(
        self,
        response: dict,
        distance_matrix: np.ndarray,
        duration_matrix: np.ndarray,
    ):
        """
        Parse OSRM API response and fill matrices.

        Args:
            response: API response dictionary
            distance_matrix: Distance matrix to fill
            duration_matrix: Duration matrix to fill
        """
        distances = response.get("distances")
        durations = response.get("durations")

        if not distances or not durations:
            raise DistanceCalculatorError("Empty matrix in API response")

        for i in range(len(distances)):
            for j in range(len(distances[i])):
                distance_matrix[i, j] = distances[i][j] / 1000.0  # Convert meters to km
                duration_matrix[i, j] = durations[i][j] / 60.0  # Convert seconds to minutes

    def _generate_cache_key(self, locations: List[Location]) -> str:
        """
        Generate a unique cache key for a set of locations.

        Args:
            locations: List of locations

        Returns:
            Cache key string
        """
        coord_str = ";".join(
            f"{loc.latitude:.6f},{loc.longitude:.6f}" for loc in locations
        )
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
            file_age = time.time() - os.path.getmtime(cache_path)
            cache_ttl_seconds = self.cache_ttl_hours * 3600

            if file_age > cache_ttl_seconds:
                os.remove(cache_path)
                return None

            with open(cache_path, "rb") as f:
                cached_data = pickle.load(f)

            if isinstance(cached_data, dict):
                return (cached_data["distance_matrix"], cached_data["duration_matrix"])
            else:
                return cached_data

        except Exception:
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
            cache_data = {
                "distance_matrix": data[0],
                "duration_matrix": data[1],
                "cached_at": datetime.now().isoformat(),
                "ttl_hours": self.cache_ttl_hours,
            }
            with open(cache_path, "wb") as f:
                pickle.dump(cache_data, f)
        except Exception:
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
            "haversine_fallbacks": self.haversine_fallbacks,
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