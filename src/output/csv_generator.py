"""
CSV output generator for VRP routing solutions.
Generates a single comprehensive CSV file with all route details.
"""
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..models.route import RoutingSolution, Route, RouteStop
from ..models.location import Depot, Hub


class CSVGenerator:
    """
    Generates CSV output files for VRP routing solutions.

    Creates a single CSV file with all route information including:
    - Source location (HUB or DEPOT)
    - Trip number
    - Vehicle information
    - Stop details
    - Timing information
    - Coordinates
    """

    def __init__(self, depot: Depot, hub: Optional[Hub] = None):
        """
        Initialize the CSV generator.

        Args:
            depot: Depot location for route information
            hub: Hub location for two-tier routing (optional)
        """
        self.depot = depot
        self.hub = hub

    def generate(
        self,
        solution: RoutingSolution,
        output_dir: str = "results",
        filename: Optional[str] = None
    ) -> Path:
        """
        Generate CSV file for the routing solution.

        Args:
            solution: RoutingSolution object containing all routes
            output_dir: Directory to save the CSV file (default: "results")
            filename: Optional custom filename (without extension)

        Returns:
            Path to the generated CSV file

        Raises:
            ValueError: If solution has no routes
        """
        if not solution.routes or solution.total_vehicles_used == 0:
            raise ValueError("Cannot generate CSV for empty solution")

        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        if filename is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"routing_result_{timestamp}"

        filepath = output_path / f"{filename}.csv"

        # Define CSV headers
        headers = [
            "Source",  # HUB or DEPOT
            "Trip #",  # Trip number
            "Vehicle Name",
            "Vehicle Type",
            "Rate (Rp/km)",
            "Sequence",
            "From",
            "To",
            "Customer",
            "Address",
            "City/Zone",
            "Delivery Time Window",
            "Arrival Time",
            "Departure Time",
            "Weight (kg)",
            "Cumulative Weight (kg)",
            "Distance from Previous (km)",
            "Latitude",
            "Longitude",
            "Priority",
            "Notes"
        ]

        # Write CSV file
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)

            # Filter out empty routes
            active_routes = [r for r in solution.routes if r.num_stops > 0]

            # Write route data
            for route in active_routes:
                # Determine starting location based on route source
                if route.source == "HUB" and self.hub:
                    previous_location = self.hub.name
                else:
                    previous_location = self.depot.name

                for stop in route.stops:
                    order = stop.order
                    current_location = order.display_name

                    # Check if this is a hub consolidation stop
                    is_hub_consolidation = order.sale_order_id == "HUB_CONSOLIDATION"

                    row = [
                        route.source,  # Source (HUB or DEPOT)
                        route.trip_number,  # Trip number
                        route.vehicle.name,  # Vehicle name
                        route.vehicle.name.split()[0],  # Vehicle type (first word)
                        route.vehicle.cost_per_km,  # Rate
                        stop.sequence + 1,  # Sequence (1-indexed for readability)
                        previous_location,  # From
                        current_location,  # To
                        order.display_name,  # Customer
                        order.alamat,  # Address
                        order.kota if hasattr(order, 'kota') else "",  # City/Zone
                        order.delivery_time,  # Delivery time window
                        stop.arrival_time_str,  # Arrival time
                        stop.departure_time_str,  # Departure time
                        f"{order.load_weight_in_kg:.1f}",  # Weight
                        f"{stop.cumulative_weight:.1f}",  # Cumulative weight
                        f"{stop.distance_from_prev:.2f}",  # Distance
                        f"{order.coordinates[0]:.6f}",  # Latitude
                        f"{order.coordinates[1]:.6f}",  # Longitude
                        "YES" if order.is_priority else "NO",  # Priority
                        "HUB CONSOLIDATION" if is_hub_consolidation else ""  # Notes
                    ]

                    writer.writerow(row)

                    # Update previous location for next iteration
                    previous_location = current_location

        return filepath

    def generate_summary_csv(
        self,
        solution: RoutingSolution,
        output_dir: str = "results",
        filename: Optional[str] = None
    ) -> Path:
        """
        Generate a summary CSV file with high-level metrics.

        Args:
            solution: RoutingSolution object
            output_dir: Directory to save the CSV file
            filename: Optional custom filename (without extension)

        Returns:
            Path to the generated summary CSV file
        """
        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        if filename is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"routing_summary_{timestamp}"

        filepath = output_path / f"{filename}.csv"

        # Calculate per-route and per-source metrics
        route_data = []
        source_metrics = {"HUB": {"routes": 0, "orders": 0, "distance": 0, "cost": 0},
                         "DEPOT": {"routes": 0, "orders": 0, "distance": 0, "cost": 0}}

        for route in solution.routes:
            if route.num_stops > 0:
                route_data.append({
                    "Source": route.source,
                    "Trip #": route.trip_number,
                    "Vehicle": route.vehicle.name,
                    "Stops": route.num_stops,
                    "Distance (km)": f"{route.total_distance:.1f}",
                    "Weight (kg)": f"{route.total_weight:.1f}",
                    "Cost (Rp)": f"{route.total_cost:,.0f}",
                    "Departure": route.departure_time_str
                })

                # Aggregate by source
                source = route.source
                source_metrics[source]["routes"] += 1
                source_metrics[source]["orders"] += route.num_stops
                source_metrics[source]["distance"] += route.total_distance
                source_metrics[source]["cost"] += route.total_cost

        # Write summary CSV
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Overall summary
            writer.writerow(["OVERALL SUMMARY"])
            writer.writerow(["Metric", "Value"])
            writer.writerow(["Total Vehicles Used", solution.total_vehicles_used])
            writer.writerow(["Total Orders Delivered", solution.total_orders_delivered])
            writer.writerow(["Total Distance (km)", f"{solution.total_distance:.1f}"])
            writer.writerow(["Total Cost (Rp)", f"{solution.total_cost:,.0f}"])
            writer.writerow(["Unassigned Orders", len(solution.unassigned_orders)])
            writer.writerow(["Optimization Strategy", solution.optimization_strategy])
            writer.writerow(["Computation Time (s)", f"{solution.computation_time:.2f}"])
            writer.writerow([])

            # Source breakdown
            writer.writerow(["BREAKDOWN BY SOURCE"])
            writer.writerow(["Source", "Routes", "Orders", "Distance (km)", "Cost (Rp)"])
            for source in ["DEPOT", "HUB"]:
                metrics = source_metrics[source]
                if metrics["routes"] > 0:
                    writer.writerow([
                        source,
                        metrics["routes"],
                        metrics["orders"],
                        f"{metrics['distance']:.1f}",
                        f"{metrics['cost']:,.0f}"
                    ])
            writer.writerow([])

            # Route details
            writer.writerow(["ROUTE DETAILS"])
            if route_data:
                headers = list(route_data[0].keys())
                writer.writerow(headers)
                for route in route_data:
                    writer.writerow(list(route.values()))

        return filepath
