"""
Dynamic source assignment for hybrid routing.

Determines optimal source (DEPOT or HUB) for each order based on cost comparison.
Supports three modes:
- zone_based: Traditional zone-based assignment (existing behavior)
- dynamic: Pure cost-based assignment
- hybrid: Dynamic with zone-based fallback
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union
import numpy as np

from ..models.order import Order
from ..models.location import Depot, Hub
from ..models.hub_config import HubConfig, MultiHubConfig, SourceAssignmentConfig


@dataclass
class SourceCost:
    """Cost breakdown for serving an order from a source."""
    source_id: str
    source_type: str  # "DEPOT" or "HUB"
    distance_km: float
    duration_minutes: float
    total_cost: float
    is_feasible: bool = True
    reason: str = ""


class DynamicSourceAssigner:
    """
    Determines optimal source (DEPOT or HUB) for each order.

    Uses hybrid approach: dynamic cost comparison + zone fallback.
    Only switches from zone-based assignment if cost advantage > threshold.
    """

    def __init__(
        self,
        depot: Depot,
        hub_configs: List[HubConfig],
        distance_matrix: np.ndarray,
        duration_matrix: np.ndarray,
        config: SourceAssignmentConfig,
        hub_index_map: Dict[str, int],  # Maps hub_id to matrix index
        order_index_offset: int = 0,  # Offset for order indices in matrix
    ):
        """
        Initialize dynamic source assigner.

        Args:
            depot: Main depot location
            hub_configs: List of hub configurations
            distance_matrix: Full distance matrix (km)
            duration_matrix: Full duration matrix (minutes)
            config: Source assignment configuration
            hub_index_map: Maps hub_id to matrix index (e.g., {"hub_utara": 1})
            order_index_offset: Starting index for orders in matrix (after depot + hubs)
        """
        self.depot = depot
        self.hub_configs = hub_configs
        self.distance_matrix = distance_matrix
        self.duration_matrix = duration_matrix
        self.config = config
        self.hub_index_map = hub_index_map
        self.order_index_offset = order_index_offset

        # Build zone to hub mapping for zone-based lookups
        self._zone_to_hub: Dict[str, str] = {}
        for hub_config in hub_configs:
            for zone in hub_config.zones_via_hub:
                self._zone_to_hub[zone.upper()] = hub_config.hub_id

        # Depot index is always 0
        self.depot_index = 0

    def compute_source_cost(
        self,
        order: Order,
        order_index: int,
        source_id: str,
    ) -> SourceCost:
        """
        Calculate weighted cost to serve order from a source.

        Cost = distance_weight * distance + time_weight * duration

        Args:
            order: The order to serve
            order_index: Index of order in orders list (0-based)
            source_id: "DEPOT" or hub_id (e.g., "hub_utara")

        Returns:
            SourceCost with cost breakdown
        """
        # Get matrix indices
        order_matrix_idx = self.order_index_offset + order_index

        if source_id == "DEPOT":
            source_matrix_idx = self.depot_index
            source_type = "DEPOT"
        else:
            if source_id not in self.hub_index_map:
                return SourceCost(
                    source_id=source_id,
                    source_type="HUB",
                    distance_km=float('inf'),
                    duration_minutes=float('inf'),
                    total_cost=float('inf'),
                    is_feasible=False,
                    reason=f"Unknown hub_id: {source_id}",
                )
            source_matrix_idx = self.hub_index_map[source_id]
            source_type = "HUB"

        # Get distance and duration from matrix
        try:
            distance_km = self.distance_matrix[source_matrix_idx][order_matrix_idx]
            duration_minutes = self.duration_matrix[source_matrix_idx][order_matrix_idx]
        except IndexError:
            return SourceCost(
                source_id=source_id,
                source_type=source_type,
                distance_km=float('inf'),
                duration_minutes=float('inf'),
                total_cost=float('inf'),
                is_feasible=False,
                reason=f"Matrix index out of bounds",
            )

        # Calculate weighted cost
        total_cost = (
            self.config.distance_weight * distance_km +
            self.config.time_weight * duration_minutes
        )

        return SourceCost(
            source_id=source_id,
            source_type=source_type,
            distance_km=distance_km,
            duration_minutes=duration_minutes,
            total_cost=total_cost,
            is_feasible=True,
        )

    def find_best_source(
        self,
        order: Order,
        order_index: int,
    ) -> Tuple[str, SourceCost]:
        """
        Find the source with lowest cost for this order.

        Args:
            order: The order to serve
            order_index: Index of order in orders list

        Returns:
            Tuple of (best_source_id, SourceCost)
        """
        # Calculate cost from depot
        depot_cost = self.compute_source_cost(order, order_index, "DEPOT")
        best_source = "DEPOT"
        best_cost = depot_cost

        # Calculate cost from each hub
        for hub_config in self.hub_configs:
            hub_cost = self.compute_source_cost(order, order_index, hub_config.hub_id)
            if hub_cost.is_feasible and hub_cost.total_cost < best_cost.total_cost:
                best_source = hub_config.hub_id
                best_cost = hub_cost

        return best_source, best_cost

    def get_zone_based_source(self, order: Order) -> str:
        """
        Get source based on zone configuration (existing behavior).

        Args:
            order: The order to route

        Returns:
            Source ID ("DEPOT" or hub_id)
        """
        if not order.kota:
            return "DEPOT"

        zone = order.kota.upper()
        return self._zone_to_hub.get(zone, "DEPOT")

    def assign_orders_dynamic(
        self,
        orders: List[Order],
    ) -> Dict[str, List[Order]]:
        """
        Assign orders to sources using pure dynamic (cost-based) assignment.

        Args:
            orders: List of orders to assign

        Returns:
            Dict mapping source_id to list of orders
        """
        result: Dict[str, List[Order]] = {"DEPOT": []}
        for hub_config in self.hub_configs:
            result[hub_config.hub_id] = []

        for idx, order in enumerate(orders):
            best_source, _ = self.find_best_source(order, idx)
            result[best_source].append(order)

        return result

    def assign_orders_hybrid(
        self,
        orders: List[Order],
        zone_assignments: Optional[Dict[str, List[Order]]] = None,
    ) -> Dict[str, List[Order]]:
        """
        Assign orders using hybrid approach: dynamic + zone fallback.

        Only switches from zone-based assignment if cost advantage exceeds threshold.

        Args:
            orders: List of orders to assign
            zone_assignments: Pre-computed zone-based assignments (optional)

        Returns:
            Dict mapping source_id to list of orders
        """
        result: Dict[str, List[Order]] = {"DEPOT": []}
        for hub_config in self.hub_configs:
            result[hub_config.hub_id] = []

        for idx, order in enumerate(orders):
            # Get zone-based assignment (fallback)
            zone_source = self.get_zone_based_source(order)
            zone_cost = self.compute_source_cost(order, idx, zone_source)

            # Find best dynamic source
            best_source, best_cost = self.find_best_source(order, idx)

            # Compare: switch only if significant advantage
            if zone_cost.is_feasible and zone_cost.total_cost > 0:
                cost_advantage_pct = (
                    (zone_cost.total_cost - best_cost.total_cost) /
                    zone_cost.total_cost * 100
                )
            else:
                cost_advantage_pct = 0

            # Decision: use dynamic only if advantage exceeds threshold
            if cost_advantage_pct >= self.config.min_cost_advantage_percent:
                final_source = best_source
            else:
                final_source = zone_source

            result[final_source].append(order)

        return result

    def assign_orders(
        self,
        orders: List[Order],
        zone_assignments: Optional[Dict[str, List[Order]]] = None,
    ) -> Dict[str, List[Order]]:
        """
        Main entry point for order assignment based on configured mode.

        Args:
            orders: List of orders to assign
            zone_assignments: Pre-computed zone-based assignments (for hybrid mode)

        Returns:
            Dict mapping source_id to list of orders
        """
        if self.config.mode == "dynamic":
            return self.assign_orders_dynamic(orders)
        elif self.config.mode == "hybrid":
            return self.assign_orders_hybrid(orders, zone_assignments)
        else:
            # Default: zone_based - should be handled by caller
            # Return empty result to signal no dynamic assignment
            return {}

    def get_assignment_summary(
        self,
        orders: List[Order],
        assignments: Dict[str, List[Order]],
    ) -> Dict:
        """
        Generate summary of assignment results.

        Args:
            orders: Original list of orders
            assignments: Assignment results

        Returns:
            Dict with summary statistics
        """
        total_orders = len(orders)
        depot_orders = len(assignments.get("DEPOT", []))
        hub_orders = sum(
            len(orders) for source, orders in assignments.items()
            if source != "DEPOT"
        )

        return {
            "total_orders": total_orders,
            "depot_orders": depot_orders,
            "hub_orders": hub_orders,
            "assignment_mode": self.config.mode,
            "cost_threshold_percent": self.config.min_cost_advantage_percent,
            "per_source": {
                source: len(orders) for source, orders in assignments.items()
            },
        }
