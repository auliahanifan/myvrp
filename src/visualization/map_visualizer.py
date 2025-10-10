"""
Map Visualization Module for VRP Routes

This module provides interactive map visualization of VRP solutions
using Folium, showing depot, customer locations, and optimized routes.
"""

import folium
from folium import plugins
from typing import List, Tuple
import random

from src.models.location import Depot
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

    def __init__(self, depot: Depot):
        """
        Initialize the map visualizer

        Args:
            depot: Depot location
        """
        self.depot = depot

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

        # Collect coordinates for the route line
        route_coords = []

        # Add depot as start point
        route_coords.append([self.depot.coordinates[0], self.depot.coordinates[1]])

        # Add customer stops
        for stop in route.stops:
            if stop.order is not None:  # Skip depot stops
                lat, lon = stop.order.coordinates
                route_coords.append([lat, lon])

                # Create marker for stop
                self._add_stop_marker(
                    route_group,
                    stop,
                    color,
                    route_number
                )

        # Add depot as end point (vehicles return to depot)
        route_coords.append([self.depot.coordinates[0], self.depot.coordinates[1]])

        # Draw route line
        folium.PolyLine(
            locations=route_coords,
            color=color,
            weight=3,
            opacity=0.7,
            tooltip=f"Route {route_number}: {route.vehicle.name}"
        ).add_to(route_group)

        # Add arrows to show direction
        self._add_route_arrows(route_group, route_coords, color)

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

    def save_map(self, solution: RoutingSolution, output_path: str):
        """
        Create and save map to HTML file

        Args:
            solution: VRP solution to visualize
            output_path: Path to save HTML file
        """
        m = self.create_map(solution)
        m.save(output_path)
