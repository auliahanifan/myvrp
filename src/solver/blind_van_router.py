"""
Blind Van Router with Mode A/B support.

Routes blind van with per-hub mode configuration:
- Mode A: Consolidation only (visit hub, drop packages)
- Mode B: Consolidation + en-route delivery (deliver orders on the way to hub)

Supports flexible return policy (can end at last hub instead of returning to depot).
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np

from ..models.order import Order
from ..models.location import Depot, Hub, Location
from ..models.vehicle import Vehicle
from ..models.route import Route, RouteStop
from ..models.hub_config import (
    HubConfig,
    MultiHubConfig,
    BlindVanMode,
    EnRouteDeliveryConfig,
)


@dataclass
class EnRouteCandidate:
    """Candidate order for en-route delivery."""
    order: Order
    order_index: int  # Index in original orders list
    segment_hub_id: str  # Hub this delivery is before
    detour_km: float  # Additional km for this detour
    detour_minutes: float  # Additional minutes for this detour
    score: float  # Lower is better


class BlindVanRouter:
    """
    Routes blind van with per-hub mode support.

    - Mode A: Consolidation only (visit hub, drop packages)
    - Mode B: Consolidation + en-route delivery
    """

    CONSOLIDATION_SERVICE_TIME = 10  # minutes to unload at hub
    DELIVERY_SERVICE_TIME = 5  # minutes per delivery stop

    def __init__(
        self,
        depot: Depot,
        hub_configs: List[HubConfig],
        orders: List[Order],
        classified_orders: Dict[str, List[Order]],
        blind_van: Vehicle,
        distance_matrix: np.ndarray,
        duration_matrix: np.ndarray,
        multi_hub_config: MultiHubConfig,
        hub_index_map: Dict[str, int],
        order_index_map: Dict[str, int],  # Maps order_id to matrix index
    ):
        """
        Initialize blind van router.

        Args:
            depot: Main depot location
            hub_configs: List of hub configurations
            orders: All orders
            classified_orders: Orders classified by source (hub_id or "DEPOT")
            blind_van: Blind van vehicle
            distance_matrix: Distance matrix (km)
            duration_matrix: Duration matrix (minutes)
            multi_hub_config: Full hub configuration
            hub_index_map: Maps hub_id to matrix index
            order_index_map: Maps order sale_order_id to matrix index
        """
        self.depot = depot
        self.hub_configs = hub_configs
        self.orders = orders
        self.classified_orders = classified_orders
        self.blind_van = blind_van
        self.distance_matrix = distance_matrix
        self.duration_matrix = duration_matrix
        self.config = multi_hub_config
        self.hub_index_map = hub_index_map
        self.order_index_map = order_index_map

        # Depot index is always 0
        self.depot_index = 0

        # Delivered orders (will be removed from DEPOT pool)
        self.delivered_en_route: List[Order] = []

    def solve(self) -> Optional[Route]:
        """
        Solve blind van routing based on per-hub modes.

        Returns:
            Route for blind van, or None if no hub orders
        """
        # 1. Identify hubs with orders
        active_hubs = self._get_active_hubs()
        if not active_hubs:
            return None

        # 2. Solve TSP for hub sequence (nearest neighbor heuristic)
        hub_sequence = self._solve_hub_tsp(active_hubs)

        # 3. For Mode B hubs, identify en-route orders
        en_route_orders = self._identify_en_route_orders(hub_sequence)

        # 4. Build final route with insertions
        route = self._build_route(hub_sequence, en_route_orders)

        return route

    def get_delivered_orders(self) -> List[Order]:
        """Get list of orders delivered en-route (to remove from DEPOT pool)."""
        return self.delivered_en_route

    def _get_active_hubs(self) -> List[HubConfig]:
        """Get hubs that have orders assigned."""
        active = []
        for hub_config in self.hub_configs:
            hub_orders = self.classified_orders.get(hub_config.hub_id, [])
            if hub_orders:
                active.append(hub_config)
        return active

    def _solve_hub_tsp(self, hubs: List[HubConfig]) -> List[HubConfig]:
        """
        Solve TSP to find optimal hub visit sequence using nearest neighbor.

        Args:
            hubs: List of hubs to visit

        Returns:
            Ordered list of hubs to visit
        """
        if len(hubs) <= 1:
            return hubs

        # Nearest neighbor heuristic starting from depot
        unvisited = list(hubs)
        sequence = []
        current_idx = self.depot_index

        while unvisited:
            best_hub = None
            best_distance = float('inf')

            for hub_config in unvisited:
                hub_idx = self.hub_index_map.get(hub_config.hub_id, -1)
                if hub_idx < 0:
                    continue
                distance = self.distance_matrix[current_idx][hub_idx]
                if distance < best_distance:
                    best_distance = distance
                    best_hub = hub_config

            if best_hub:
                sequence.append(best_hub)
                unvisited.remove(best_hub)
                current_idx = self.hub_index_map[best_hub.hub_id]
            else:
                # Fallback: add remaining in original order
                sequence.extend(unvisited)
                break

        return sequence

    def _identify_en_route_orders(
        self,
        hub_sequence: List[HubConfig]
    ) -> Dict[str, List[Order]]:
        """
        For Mode B hubs, find orders that can be delivered en-route.

        Returns:
            Dict mapping hub_id to orders to deliver before reaching that hub
        """
        en_route: Dict[str, List[Order]] = {}

        # Get DEPOT orders (candidates for en-route delivery)
        depot_orders = list(self.classified_orders.get("DEPOT", []))
        if not depot_orders:
            return en_route

        # Track which orders have been selected
        selected_order_ids = set()

        for i, hub_config in enumerate(hub_sequence):
            # Skip if not Mode B with delivery enabled
            if not hub_config.blind_van_config.is_delivery_enabled:
                continue

            config = hub_config.blind_van_config.en_route_delivery
            if config.max_stops == 0:
                continue

            # Get segment: previous_stop -> this_hub
            if i == 0:
                prev_idx = self.depot_index
            else:
                prev_hub = hub_sequence[i - 1]
                prev_idx = self.hub_index_map.get(prev_hub.hub_id, self.depot_index)

            hub_idx = self.hub_index_map.get(hub_config.hub_id, -1)
            if hub_idx < 0:
                continue

            # Find candidates in corridor
            candidates = self._find_corridor_candidates(
                prev_idx,
                hub_idx,
                depot_orders,
                config,
                hub_config.hub_id,
                selected_order_ids,
            )

            # Select best orders
            selected = self._select_en_route_orders(candidates, config)

            # Track selected orders
            for order in selected:
                selected_order_ids.add(order.sale_order_id)
                self.delivered_en_route.append(order)

            en_route[hub_config.hub_id] = selected

        return en_route

    def _find_corridor_candidates(
        self,
        start_idx: int,
        end_idx: int,
        depot_orders: List[Order],
        config: EnRouteDeliveryConfig,
        hub_id: str,
        excluded_ids: set,
    ) -> List[EnRouteCandidate]:
        """
        Find orders within delivery corridor between two points.

        Corridor = orders where detour is within max_detour_km and max_detour_minutes.
        """
        candidates = []

        # Direct distance/time from start to end
        direct_distance = self.distance_matrix[start_idx][end_idx]
        direct_duration = self.duration_matrix[start_idx][end_idx]

        for order in depot_orders:
            # Skip already selected orders
            if order.sale_order_id in excluded_ids:
                continue

            # Get order matrix index
            order_idx = self.order_index_map.get(order.sale_order_id, -1)
            if order_idx < 0:
                continue

            # Calculate detour: start -> order -> end vs start -> end
            dist_to_order = self.distance_matrix[start_idx][order_idx]
            dist_order_to_end = self.distance_matrix[order_idx][end_idx]
            total_distance = dist_to_order + dist_order_to_end

            time_to_order = self.duration_matrix[start_idx][order_idx]
            time_order_to_end = self.duration_matrix[order_idx][end_idx]
            total_time = time_to_order + time_order_to_end + self.DELIVERY_SERVICE_TIME

            detour_km = total_distance - direct_distance
            detour_minutes = total_time - direct_duration

            # Check if within corridor constraints
            if detour_km <= config.max_detour_km and detour_minutes <= config.max_detour_minutes:
                # Score: prefer lower detour and lighter weight
                score = detour_km * 2 + detour_minutes / 10

                candidates.append(EnRouteCandidate(
                    order=order,
                    order_index=order_idx,
                    segment_hub_id=hub_id,
                    detour_km=detour_km,
                    detour_minutes=detour_minutes,
                    score=score,
                ))

        return candidates

    def _select_en_route_orders(
        self,
        candidates: List[EnRouteCandidate],
        config: EnRouteDeliveryConfig,
    ) -> List[Order]:
        """
        Select best en-route orders from candidates.

        Prioritize: lowest score (detour), fits in reserved capacity.
        """
        if not candidates:
            return []

        # Sort by score (lowest first)
        sorted_candidates = sorted(candidates, key=lambda c: c.score)

        # Calculate available capacity for en-route delivery
        total_consolidation_weight = self._get_total_consolidation_weight()
        available_capacity = self.blind_van.capacity - total_consolidation_weight - config.reserve_capacity_kg

        selected = []
        total_weight = 0

        for candidate in sorted_candidates:
            if len(selected) >= config.max_stops:
                break

            order_weight = candidate.order.load_weight_in_kg
            if total_weight + order_weight > available_capacity:
                continue

            selected.append(candidate.order)
            total_weight += order_weight

        return selected

    def _get_total_consolidation_weight(self) -> float:
        """Calculate total weight of all hub consolidation orders."""
        total = 0.0
        for hub_config in self.hub_configs:
            hub_orders = self.classified_orders.get(hub_config.hub_id, [])
            total += sum(o.load_weight_in_kg for o in hub_orders)
        return total

    def _build_route(
        self,
        hub_sequence: List[HubConfig],
        en_route_orders: Dict[str, List[Order]],
    ) -> Route:
        """
        Build final blind van route with hub visits and en-route deliveries.
        """
        stops = []
        current_time = self.config.blind_van_departure
        prev_idx = self.depot_index

        # Calculate initial weight (consolidation + en-route)
        current_weight = self._get_total_consolidation_weight()
        for orders in en_route_orders.values():
            current_weight += sum(o.load_weight_in_kg for o in orders)

        total_distance = 0.0

        for hub_config in hub_sequence:
            hub_idx = self.hub_index_map.get(hub_config.hub_id, -1)
            if hub_idx < 0:
                continue

            # Add en-route deliveries BEFORE this hub
            for order in en_route_orders.get(hub_config.hub_id, []):
                order_idx = self.order_index_map.get(order.sale_order_id, -1)
                if order_idx < 0:
                    continue

                # Travel to order
                travel_distance = self.distance_matrix[prev_idx][order_idx]
                travel_time = self.duration_matrix[prev_idx][order_idx]
                total_distance += travel_distance

                arrival_time = int(current_time + travel_time)
                departure_time = arrival_time + self.DELIVERY_SERVICE_TIME

                stops.append(RouteStop(
                    order=order,
                    arrival_time=arrival_time,
                    departure_time=departure_time,
                    distance_from_prev=travel_distance,
                    cumulative_weight=current_weight,
                    sequence=len(stops) + 1,
                ))

                current_time = departure_time
                current_weight -= order.load_weight_in_kg
                prev_idx = order_idx

            # Add hub stop (consolidation drop-off)
            travel_distance = self.distance_matrix[prev_idx][hub_idx]
            travel_time = self.duration_matrix[prev_idx][hub_idx]
            total_distance += travel_distance

            arrival_time = int(current_time + travel_time)
            departure_time = arrival_time + self.CONSOLIDATION_SERVICE_TIME

            # Create consolidation pseudo-order
            hub_order = self._create_consolidation_order(hub_config)

            stops.append(RouteStop(
                order=hub_order,
                arrival_time=arrival_time,
                departure_time=departure_time,
                distance_from_prev=travel_distance,
                cumulative_weight=current_weight,
                sequence=len(stops) + 1,
            ))

            current_time = departure_time
            current_weight -= hub_order.load_weight_in_kg
            prev_idx = hub_idx

        # Return to depot if configured
        if self.config.blind_van_return_to_depot:
            return_distance = self.distance_matrix[prev_idx][self.depot_index]
            total_distance += return_distance

        return Route(
            vehicle=self.blind_van,
            stops=stops,
            total_distance=total_distance,
            total_cost=total_distance * self.blind_van.cost_per_km,
            departure_time=self.config.blind_van_departure,
            source="DEPOT",
            trip_number=1,
        )

    def _create_consolidation_order(self, hub_config: HubConfig) -> Order:
        """Create a pseudo-order for hub consolidation."""
        hub_orders = self.classified_orders.get(hub_config.hub_id, [])
        total_weight = sum(o.load_weight_in_kg for o in hub_orders)

        # Get delivery date from first hub order, or use today's date
        delivery_date = "2025-01-01"  # Default fallback
        if hub_orders:
            delivery_date = hub_orders[0].delivery_date
        elif self.orders:
            delivery_date = self.orders[0].delivery_date

        return Order(
            sale_order_id=f"HUB_CONSOLIDATION_{hub_config.hub_id}",
            delivery_date=delivery_date,
            delivery_time="05:30-06:00",
            load_weight_in_kg=total_weight,
            partner_id=hub_config.hub_id,
            display_name=f"Consolidation to {hub_config.hub.name}",
            alamat=hub_config.hub.address or hub_config.hub.name,
            coordinates=hub_config.hub.coordinates,
            is_priority=True,  # Hub delivery is always priority
        )

    def get_route_summary(self, route: Route) -> Dict:
        """Generate summary of blind van route."""
        delivery_stops = [s for s in route.stops if not s.order.sale_order_id.startswith("HUB_CONSOLIDATION")]
        consolidation_stops = [s for s in route.stops if s.order.sale_order_id.startswith("HUB_CONSOLIDATION")]

        return {
            "total_stops": len(route.stops),
            "delivery_stops": len(delivery_stops),
            "hub_stops": len(consolidation_stops),
            "total_distance_km": route.total_distance,
            "total_cost": route.total_cost,
            "departure_time": route.departure_time_str,
            "return_to_depot": self.config.blind_van_return_to_depot,
            "en_route_deliveries": [o.sale_order_id for o in self.delivered_en_route],
        }
