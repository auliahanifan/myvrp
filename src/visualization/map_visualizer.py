"""
Map Visualization Module for VRP Routes

This module provides interactive map visualization of VRP solutions
using Folium, showing depot, customer locations, and optimized routes.
"""

import folium
from folium import plugins
from typing import List, Tuple, Optional
import random
import requests
import polyline
import os
import hashlib
import json
from pathlib import Path
import logging
import concurrent.futures
import time

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from src.models.location import Depot, Hub
from src.models.route import RoutingSolution, Route


class MapVisualizer:
    """Creates interactive maps for VRP solutions using Folium"""

    # Color palette for different routes
    COLORS = [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
        '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B739', '#52B788',
        '#E63946', '#457B9D', '#A8DADC', '#F77F00', '#06D6A0',
        '#118AB2', '#073B4C', '#EF476F', '#FFD166', '#06FFA5'
    ]

    def __init__(self, depot: Depot, hub: Optional[Hub] = None, enable_road_routing: bool = True):
        """
        Initialize the map visualizer

        Args:
            depot: Depot location
            hub: Hub location (optional, for two-tier routing)
            enable_road_routing: Whether to use actual road paths vs straight lines
        """
        self.depot = depot
        self.hub = hub
        self.osrm_url = "https://osrm.segarloka.cc"
        self.enable_road_routing = enable_road_routing

        # Cache directory for route geometries
        self.cache_dir = Path(".cache/route_geometry")
        if self.enable_road_routing:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def create_map(self, solution: RoutingSolution, zoom_start: int = 12) -> folium.Map:
        """
        Create an interactive Folium map with routes

        Args:
            solution: VRP solution to visualize
            zoom_start: Initial zoom level (default: 12)

        Returns:
            Folium map object
        """
        # Center map on depot
        m = folium.Map(
            location=[self.depot.coordinates[0], self.depot.coordinates[1]],
            zoom_start=zoom_start,
            tiles='OpenStreetMap'
        )

        # Add depot marker
        self._add_depot_marker(m)

        # Add hub marker if hub is enabled
        if self.hub:
            self._add_hub_marker(m)

        # Add routes with different colors
        for idx, route in enumerate(solution.routes):
            color = self.COLORS[idx % len(self.COLORS)]
            self._add_route(m, route, color, idx + 1)

        # Add legend
        self._add_legend(m, solution)

        # Add map controls
        folium.plugins.Fullscreen().add_to(m)
        folium.plugins.MeasureControl().add_to(m)

        # Fit bounds to show all markers
        self._fit_bounds(m, solution)

        return m

    def create_single_route_map(self, solution: RoutingSolution, route_idx: int, zoom_start: int = 13) -> folium.Map:
        """
        Create an interactive Folium map showing only a single route

        Args:
            solution: VRP solution to visualize
            route_idx: Index of the route to display
            zoom_start: Initial zoom level (default: 13, closer zoom for single route)

        Returns:
            Folium map object
        """
        if route_idx < 0 or route_idx >= len(solution.routes):
            raise ValueError(f"Invalid route index: {route_idx}")

        selected_route = solution.routes[route_idx]

        # Center map on depot
        m = folium.Map(
            location=[self.depot.coordinates[0], self.depot.coordinates[1]],
            zoom_start=zoom_start,
            tiles='OpenStreetMap'
        )

        # Add depot marker
        self._add_depot_marker(m)

        # Add hub marker if hub is enabled
        if self.hub:
            self._add_hub_marker(m)

        # Add only the selected route with highlighted color
        color = '#FF0000'  # Bright red for single route
        self._add_route(m, selected_route, color, route_idx + 1)

        # Add single route legend
        self._add_single_route_legend(m, selected_route, route_idx + 1)

        # Add map controls
        folium.plugins.Fullscreen().add_to(m)
        folium.plugins.MeasureControl().add_to(m)

        # Fit bounds to show only this route
        self._fit_single_route_bounds(m, selected_route)

        return m

    def _add_depot_marker(self, m: folium.Map):
        """Add depot marker to map"""
        folium.Marker(
            location=[self.depot.coordinates[0], self.depot.coordinates[1]],
            popup=folium.Popup(
                f"<b>🏭 DEPOT</b><br>"
                f"{self.depot.name}<br>"
                f"{self.depot.address}<br>"
                f"<i>{self.depot.coordinates[0]:.6f}, {self.depot.coordinates[1]:.6f}</i>",
                max_width=300
            ),
            tooltip="🏭 Depot",
            icon=folium.Icon(
                color='red',
                icon='home',
                prefix='fa'
            )
        ).add_to(m)

        # Add a circle around depot
        folium.Circle(
            location=[self.depot.coordinates[0], self.depot.coordinates[1]],
            radius=200,
            color='red',
            fill=True,
            fillColor='red',
            fillOpacity=0.1,
            weight=2,
            opacity=0.5
        ).add_to(m)

    def _add_hub_marker(self, m: folium.Map):
        """Add hub marker to map for two-tier routing"""
        if not self.hub:
            return

        folium.Marker(
            location=[self.hub.coordinates[0], self.hub.coordinates[1]],
            popup=folium.Popup(
                f"<b>📦 HUB</b><br>"
                f"{self.hub.name}<br>"
                f"{self.hub.address}<br>"
                f"<i>{self.hub.coordinates[0]:.6f}, {self.hub.coordinates[1]:.6f}</i>",
                max_width=300
            ),
            tooltip="📦 Hub (Consolidation Point)",
            icon=folium.Icon(
                color='blue',
                icon='cube',
                prefix='fa'
            )
        ).add_to(m)

        # Add a circle around hub (larger than depot)
        folium.Circle(
            location=[self.hub.coordinates[0], self.hub.coordinates[1]],
            radius=300,
            color='blue',
            fill=True,
            fillColor='blue',
            fillOpacity=0.15,
            weight=2,
            opacity=0.6
        ).add_to(m)

        # Add label text
        folium.Marker(
            location=[self.hub.coordinates[0], self.hub.coordinates[1]],
            popup="📦 Hub",
            icon=folium.DivIcon(html="""
                <div style="font-size: 12px; color: blue; font-weight: bold;
                            background-color: white; padding: 3px 6px;
                            border-radius: 3px; border: 1px solid blue;">
                    HUB
                </div>
            """)
        ).add_to(m)

    def _get_road_path_with_retry(self, start_coords: Tuple[float, float], end_coords: Tuple[float, float], max_retries: int = 3) -> List[List[float]]:
        """
        Get road path with retry logic for transient failures

        Args:
            start_coords: (lat, lon) starting coordinates
            end_coords: (lat, lon) ending coordinates
            max_retries: Maximum number of retry attempts

        Returns:
            List of [lat, lon] coordinates representing the road path
        """
        for attempt in range(max_retries):
            try:
                path = self._get_road_path(start_coords, end_coords)
                # Check if we got a real path (more than 2 points) or just a straight line fallback
                if len(path) > 2:
                    return path
                elif attempt == max_retries - 1:
                    # Last attempt, accept the fallback
                    return path
                else:
                    # Straight line fallback on non-final attempt, retry
                    logger.debug(f"Retry {attempt + 1}/{max_retries} for {start_coords} -> {end_coords}")
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.warning(f"All retries failed for {start_coords} -> {end_coords}: {e}")
                    return [list(start_coords), list(end_coords)]
                time.sleep(0.5 * (attempt + 1))

        # Should not reach here, but fallback just in case
        return [list(start_coords), list(end_coords)]

    def _get_road_path(self, start_coords: Tuple[float, float], end_coords: Tuple[float, float]) -> List[List[float]]:
        """
        Get actual road path between two coordinates using OSRM Route API

        Args:
            start_coords: (lat, lon) starting coordinates
            end_coords: (lat, lon) ending coordinates

        Returns:
            List of [lat, lon] coordinates representing the road path
        """
        if not self.enable_road_routing:
            # Return straight line if road routing disabled
            return [list(start_coords), list(end_coords)]

        # Create cache key from coordinates
        cache_key = hashlib.md5(
            f"{start_coords[0]},{start_coords[1]}|{end_coords[0]},{end_coords[1]}".encode()
        ).hexdigest()
        cache_file = self.cache_dir / f"{cache_key}.json"

        # Check cache first
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                    logger.debug(f"Cache hit for path {start_coords} -> {end_coords}")
                    return cached_data['path']
            except:
                pass  # Cache read failed, fetch from API

        # Fetch from OSRM API
        try:
            lon1, lat1 = start_coords[1], start_coords[0]
            lon2, lat2 = end_coords[1], end_coords[0]
            url = f"{self.osrm_url}/route/v1/car/{lon1},{lat1};{lon2},{lat2}"
            params = {
                "overview": "full",
                "geometries": "polyline"
            }

            response = requests.get(url, params=params, timeout=30)  # Increased timeout to 30s

            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 'Ok' and data.get('routes'):
                    route_geometry = data['routes'][0]['geometry']
                    decoded = polyline.decode(route_geometry)
                    path = [[lat, lon] for lat, lon in decoded]

                    # Cache the result
                    try:
                        with open(cache_file, 'w') as f:
                            json.dump({"path": path}, f)
                        logger.debug(f"Cached road path: {start_coords} -> {end_coords}")
                    except Exception as e:
                        logger.warning(f"Failed to cache path: {e}")

                    return path
                else:
                    # OSRM returned error response
                    logger.warning(f"OSRM API error: {data.get('code', 'Unknown')} - {data.get('message', 'No message')} for {start_coords} -> {end_coords}")
            else:
                logger.warning(f"OSRM API HTTP error {response.status_code} for {start_coords} -> {end_coords}")

        except requests.exceptions.Timeout as e:
            logger.debug(f"OSRM API timeout for {start_coords} -> {end_coords}: {e}")
        except requests.exceptions.RequestException as e:
            logger.debug(f"OSRM API request error for {start_coords} -> {end_coords}: {e}")
        except Exception as e:
            logger.debug(f"Unexpected error fetching road path for {start_coords} -> {end_coords}: {e}")

        # Fallback to straight line (always works)
        logger.debug(f"Using straight line fallback for {start_coords} -> {end_coords}")
        return [list(start_coords), list(end_coords)]

    def _add_route(self, m: folium.Map, route: Route, color: str, route_number: int):
        """
        Add a single route to the map

        Args:
            m: Folium map object
            route: Route to add
            color: Color for this route
            route_number: Route sequence number
        """
        # Create feature group for this route (for layer control)
        route_group = folium.FeatureGroup(
            name=f"Route {route_number}: {route.vehicle.name}",
            show=True
        )

        # Build list of waypoints (start location -> stops -> return to start)
        # Determine starting location based on route source
        if route.source == "HUB" and self.hub:
            start_coords = [self.hub.coordinates[0], self.hub.coordinates[1]]
        else:
            start_coords = [self.depot.coordinates[0], self.depot.coordinates[1]]
        waypoints = [start_coords]

        # Add customer stops and create markers
        for stop in route.stops:
            if stop.order is not None:  # Skip depot stops
                lat, lon = stop.order.coordinates
                waypoints.append([lat, lon])

                # Create marker for stop
                self._add_stop_marker(
                    route_group,
                    stop,
                    color,
                    route_number
                )

        # Add end point (vehicles return to their starting location)
        if route.source == "HUB" and self.hub:
            end_coords = [self.hub.coordinates[0], self.hub.coordinates[1]]
        else:
            end_coords = [self.depot.coordinates[0], self.depot.coordinates[1]]
        waypoints.append(end_coords)

        # Draw route lines using actual road paths
        all_road_coords = []
        
        # Prepare tasks for parallel execution
        tasks = []
        for i in range(len(waypoints) - 1):
            start_coords = tuple(waypoints[i])
            end_coords = tuple(waypoints[i + 1])
            tasks.append((start_coords, end_coords))

        # Execute in parallel with retry logic
        start_time = time.time()
        # Use ThreadPoolExecutor to fetch segments in parallel
        # Reduced workers to 5 to avoid overwhelming the API
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all tasks
            future_to_index = {
                executor.submit(self._get_road_path_with_retry, start, end): i
                for i, (start, end) in enumerate(tasks)
            }

            # Collect results in order
            results = [None] * len(tasks)
            for future in concurrent.futures.as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    logger.error(f"Error fetching road path segment {index} after retries: {e}")
                    # Fallback to straight line
                    results[index] = [list(tasks[index][0]), list(tasks[index][1])]

        # Combine results and count successful vs fallback paths
        successful_paths = 0
        fallback_paths = 0
        for path in results:
            if path:
                all_road_coords.extend(path)
                # Paths with >2 points are actual road paths, =2 points are straight line fallbacks
                if len(path) > 2:
                    successful_paths += 1
                else:
                    fallback_paths += 1

        elapsed = time.time() - start_time
        logger.info(f"Route {route_number} path generation took {elapsed:.2f}s for {len(tasks)} segments "
                   f"(✅ {successful_paths} road paths, ⚠️ {fallback_paths} straight lines)")

        # Draw the complete route with road following
        if all_road_coords:
            folium.PolyLine(
                locations=all_road_coords,
                color=color,
                weight=4,
                opacity=0.8,
                tooltip=f"Route {route_number}: {route.vehicle.name}"
            ).add_to(route_group)

            # Add arrows to show direction (use waypoints, not all road coords)
            self._add_route_arrows(route_group, waypoints, color)

        # Add route group to map
        route_group.add_to(m)

    def _add_stop_marker(self, route_group: folium.FeatureGroup, stop, color: str, route_number: int):
        """Add a marker for a customer stop"""
        lat, lon = stop.order.coordinates

        # Determine marker icon based on priority
        icon_color = 'orange' if stop.order.is_priority else 'blue'
        icon_symbol = 'star' if stop.order.is_priority else 'circle'

        # Create popup HTML with detailed information
        popup_html = f"""
        <div style='min-width: 250px'>
            <h4 style='margin: 0 0 10px 0; color: {color};'>
                🚚 Stop #{stop.sequence + 1} - Route {route_number}
            </h4>
            <table style='width: 100%; font-size: 12px;'>
                <tr>
                    <td><b>Customer:</b></td>
                    <td>{stop.order.display_name}</td>
                </tr>
                <tr>
                    <td><b>Address:</b></td>
                    <td>{stop.order.alamat}</td>
                </tr>
                <tr>
                    <td><b>Order ID:</b></td>
                    <td>{stop.order.sale_order_id}</td>
                </tr>
                <tr>
                    <td><b>Weight:</b></td>
                    <td>{stop.order.load_weight_in_kg:.1f} kg</td>
                </tr>
                <tr>
                    <td><b>Cumulative:</b></td>
                    <td>{stop.cumulative_weight:.1f} kg</td>
                </tr>
                <tr>
                    <td><b>Delivery Window:</b></td>
                    <td>{stop.order.delivery_time}</td>
                </tr>
                <tr>
                    <td><b>Arrival:</b></td>
                    <td>{stop.arrival_time_str}</td>
                </tr>
                <tr>
                    <td><b>Departure:</b></td>
                    <td>{stop.departure_time_str}</td>
                </tr>
                <tr>
                    <td><b>Priority:</b></td>
                    <td>{'⭐ YES' if stop.order.is_priority else 'No'}</td>
                </tr>
                <tr>
                    <td><b>Distance from prev:</b></td>
                    <td>{stop.distance_from_prev:.2f} km</td>
                </tr>
            </table>
        </div>
        """

        # Create marker
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=350),
            tooltip=f"Stop {stop.sequence + 1}: {stop.order.display_name}",
            icon=folium.Icon(
                color=icon_color,
                icon=icon_symbol,
                prefix='fa'
            )
        ).add_to(route_group)

        # Add circle marker with sequence number
        folium.CircleMarker(
            location=[lat, lon],
            radius=8,
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.3,
            weight=2,
            opacity=0.8
        ).add_to(route_group)

    def _add_route_arrows(self, route_group: folium.FeatureGroup, coords: List[Tuple[float, float]], color: str):
        """Add directional arrows along the route"""
        if len(coords) < 2:
            return

        # Add arrows every few segments
        arrow_frequency = max(1, len(coords) // 5)

        for i in range(0, len(coords) - 1, arrow_frequency):
            # Get midpoint
            lat1, lon1 = coords[i]
            lat2, lon2 = coords[i + 1]
            mid_lat = (lat1 + lat2) / 2
            mid_lon = (lon1 + lon2) / 2

            # Calculate angle
            import math
            angle = math.degrees(math.atan2(lon2 - lon1, lat2 - lat1))

            # Add arrow marker
            folium.RegularPolygonMarker(
                location=[mid_lat, mid_lon],
                fill_color=color,
                fill_opacity=0.8,
                color=color,
                number_of_sides=3,
                radius=5,
                rotation=angle
            ).add_to(route_group)

    def _add_legend(self, m: folium.Map, solution: RoutingSolution):
        """Add a legend to the map"""
        legend_html = f"""
        <div style="position: fixed;
                    bottom: 50px; right: 50px;
                    width: 300px;
                    background-color: white;
                    border: 2px solid grey;
                    border-radius: 5px;
                    padding: 10px;
                    font-size: 14px;
                    z-index: 9999;
                    box-shadow: 2px 2px 6px rgba(0,0,0,0.3);">
            <h4 style="margin-top: 0;">📊 Route Summary</h4>
            <table style="width: 100%; font-size: 12px;">
                <tr>
                    <td><b>Total Routes:</b></td>
                    <td>{solution.total_vehicles_used}</td>
                </tr>
                <tr>
                    <td><b>Total Orders:</b></td>
                    <td>{solution.total_orders_delivered}</td>
                </tr>
                <tr>
                    <td><b>Total Distance:</b></td>
                    <td>{solution.total_distance:.1f} km</td>
                </tr>
                <tr>
                    <td><b>Total Cost:</b></td>
                    <td>Rp {solution.total_cost:,.0f}</td>
                </tr>
            </table>
            <hr style="margin: 10px 0;">
            <div style="font-size: 11px;">
                <div><span style="color: red;">🏭</span> Depot</div>
                <div><span style="color: orange;">⭐</span> Priority Order</div>
                <div><span style="color: blue;">⚫</span> Regular Order</div>
            </div>
        </div>
        """

        m.get_root().html.add_child(folium.Element(legend_html))

    def _fit_bounds(self, m: folium.Map, solution: RoutingSolution):
        """Fit map bounds to show all locations"""
        # Collect all coordinates
        all_coords = [[self.depot.coordinates[0], self.depot.coordinates[1]]]

        for route in solution.routes:
            for stop in route.stops:
                if stop.order is not None:
                    all_coords.append([stop.order.coordinates[0], stop.order.coordinates[1]])

        if len(all_coords) > 1:
            m.fit_bounds(all_coords)

    def _fit_single_route_bounds(self, m: folium.Map, route: Route):
        """Fit map bounds to show single route"""
        # Collect all coordinates for this route
        all_coords = [[self.depot.coordinates[0], self.depot.coordinates[1]]]

        for stop in route.stops:
            if stop.order is not None:
                all_coords.append([stop.order.coordinates[0], stop.order.coordinates[1]])

        if len(all_coords) > 1:
            m.fit_bounds(all_coords)

    def _add_single_route_legend(self, m: folium.Map, route: Route, route_number: int):
        """Add a legend for single route view"""
        legend_html = f"""
        <div style="position: fixed;
                    bottom: 50px; right: 50px;
                    width: 320px;
                    background-color: white;
                    border: 2px solid #FF0000;
                    border-radius: 5px;
                    padding: 10px;
                    font-size: 14px;
                    z-index: 9999;
                    box-shadow: 2px 2px 6px rgba(0,0,0,0.3);">
            <h4 style="margin-top: 0; color: #FF0000;">🚚 Route #{route_number}</h4>
            <table style="width: 100%; font-size: 12px;">
                <tr>
                    <td><b>Vehicle:</b></td>
                    <td>{route.vehicle.name}</td>
                </tr>
                <tr>
                    <td><b>Capacity:</b></td>
                    <td>{route.total_weight:.1f} / {route.vehicle.capacity} kg</td>
                </tr>
                <tr>
                    <td><b>Stops:</b></td>
                    <td>{route.num_stops} deliveries</td>
                </tr>
                <tr>
                    <td><b>Distance:</b></td>
                    <td>{route.total_distance:.1f} km</td>
                </tr>
                <tr>
                    <td><b>Cost:</b></td>
                    <td>Rp {route.total_cost:,.0f}</td>
                </tr>
                <tr>
                    <td><b>Depart:</b></td>
                    <td>{route.departure_time_str}</td>
                </tr>
            </table>
            <hr style="margin: 10px 0;">
            <div style="font-size: 11px;">
                <div><span style="color: red;">🏭</span> Depot</div>
                <div><span style="color: orange;">⭐</span> Priority Order</div>
                <div><span style="color: blue;">⚫</span> Regular Order</div>
            </div>
        </div>
        """

        m.get_root().html.add_child(folium.Element(legend_html))

    def save_map(self, solution: RoutingSolution, output_path: str):
        """
        Create and save map to HTML file

        Args:
            solution: VRP solution to visualize
            output_path: Path to save HTML file
        """
        m = self.create_map(solution)
        m.save(output_path)

    def save_single_route_map(self, solution: RoutingSolution, route_idx: int, output_path: str):
        """
        Create and save single route map to HTML file

        Args:
            solution: VRP solution to visualize
            route_idx: Index of the route to display
            output_path: Path to save HTML file
        """
        m = self.create_single_route_map(solution, route_idx)
        m.save(output_path)
