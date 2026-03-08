from __future__ import annotations

from typing import Any

from src.models.location import Depot
from src.models.route import RoutingSolution


class ResultsService:
    def build_summary_metrics(self, solution: RoutingSolution) -> dict[str, Any]:
        average_distance = (
            solution.total_distance / solution.total_vehicles_used
            if solution.total_vehicles_used
            else 0.0
        )
        average_orders = (
            solution.total_orders_delivered / solution.total_vehicles_used
            if solution.total_vehicles_used
            else 0.0
        )

        return {
            "total_vehicles": solution.total_vehicles_used,
            "total_orders": solution.total_orders_delivered,
            "total_distance_km": solution.total_distance,
            "total_cost": solution.total_cost,
            "avg_distance_per_vehicle": average_distance,
            "avg_orders_per_vehicle": average_orders,
            "optimization_strategy": solution.optimization_strategy,
            "unassigned_orders": len(solution.unassigned_orders),
        }

    def build_unassigned_rows(self, solution: RoutingSolution) -> list[dict[str, Any]]:
        return [
            {
                "Customer": order.display_name,
                "Address": order.alamat,
                "Delivery Time": order.delivery_time,
                "Weight (kg)": order.load_weight_in_kg,
                "Priority": "✅" if order.is_priority else "",
            }
            for order in solution.unassigned_orders
        ]

    def build_route_rows(
        self,
        solution: RoutingSolution,
        depot: Depot,
        hubs_config=None,
    ) -> list[dict[str, Any]]:
        rows = []
        for route in solution.routes:
            if route.source != "DEPOT" and hubs_config:
                hub_config = hubs_config.get_hub_by_id(route.source)
                previous_location = hub_config.hub.name if hub_config else depot.name
            else:
                previous_location = depot.name

            for stop in route.stops:
                order = stop.order
                rows.append(
                    {
                        "Source": route.source,
                        "Trip #": route.trip_number,
                        "From": previous_location,
                        "To": order.display_name,
                        "Vehicle": route.vehicle.name,
                        "Sequence": stop.sequence + 1,
                        "Location": "📦 HUB"
                        if order.sale_order_id == "HUB_CONSOLIDATION"
                        else "🏠 Customer",
                        "Customer": order.display_name,
                        "Address": order.alamat,
                        "City/Zone": order.kota or "-",
                        "Delivery Time": order.delivery_time,
                        "Arrival": stop.arrival_time_str,
                        "Departure": stop.departure_time_str,
                        "Weight (kg)": f"{order.load_weight_in_kg:.1f}",
                        "Cumulative Weight (kg)": f"{stop.cumulative_weight:.1f}",
                        "Distance (km)": f"{stop.distance_from_prev:.2f}",
                        "Priority": "✅" if order.is_priority else "",
                    }
                )
                previous_location = order.display_name
        return rows

    def build_vehicle_options(self, solution: RoutingSolution) -> list[str]:
        vehicle_names = []
        for route in solution.routes:
            if route.vehicle.name not in vehicle_names:
                vehicle_names.append(route.vehicle.name)

        if "Blind Van" in vehicle_names:
            vehicle_names.remove("Blind Van")
            vehicle_names.insert(0, "Blind Van")
        return vehicle_names
