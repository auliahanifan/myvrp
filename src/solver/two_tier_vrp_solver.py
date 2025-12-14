"""
Multi-Hub VRP Solver for Hub-based consolidation routing.

Supports 0 to N hubs with:
- Zero Hub Mode: All orders routed directly from DEPOT
- Single Hub Mode: Traditional two-tier (Blind Van + Motors)
- Multi Hub Mode: Blind Van TSP tour to all hubs, Motors from each hub/DEPOT

Features:
- Per-hub blind van modes (Mode A: consolidation only, Mode B: consolidation + delivery)
- Hybrid source assignment (dynamic cost-based + zone fallback)
- Flexible blind van return policy (can end at last hub)

Tier 1: Blind Van consolidates bulk delivery to hubs (DEPOT -> Hub1 -> Hub2 -> [DEPOT])
Tier 2: Motors from each hub serve that hub's orders, Motors from DEPOT serve direct orders
"""
from typing import List, Tuple, Optional, Dict
import numpy as np
import time as time_module

from ..models.order import Order
from ..models.vehicle import VehicleFleet, Vehicle
from ..models.location import Depot, Hub, Location
from ..models.route import Route, RouteStop, RoutingSolution
from ..models.hub_config import MultiHubConfig, HubConfig, HubIndexManager
from ..utils.hub_routing import MultiHubRoutingManager
from .vrp_solver import VRPSolver
from .multi_trip_solver import MultiTripSolver
from .dynamic_source_assigner import DynamicSourceAssigner
from .blind_van_router import BlindVanRouter


class TwoTierRoutingError(Exception):
    """Custom exception for two-tier routing errors."""
    pass


class MultiHubVRPSolver:
    """
    Multi-hub two-tier routing solver.

    Modes:
    - Zero Hub: All orders from DEPOT (single-tier VRP)
    - Single Hub: DEPOT -> HUB -> DEPOT, then Motors from HUB/DEPOT
    - Multi Hub: DEPOT -> Hub1 -> Hub2 -> ... -> DEPOT (TSP), then Motors from each hub

    Matrix Structure:
    - Index 0: DEPOT
    - Index 1 to N: HUB_1, HUB_2, ..., HUB_N
    - Index N+1 onwards: Customers
    """

    def __init__(
        self,
        orders: List[Order],
        fleet: VehicleFleet,
        depot: Depot,
        multi_hub_config: MultiHubConfig,
        hub_routing_manager: MultiHubRoutingManager,
        full_distance_matrix: np.ndarray,
        full_duration_matrix: np.ndarray,
        config: dict = None,
    ):
        """
        Initialize multi-hub VRP solver.

        Args:
            orders: List of all orders
            fleet: Vehicle fleet (may include Blind Van and Motors)
            depot: Main depot location
            multi_hub_config: MultiHubConfig with all hub configurations
            hub_routing_manager: MultiHubRoutingManager for order classification
            full_distance_matrix: Distance matrix [DEPOT, HUB_1, ..., HUB_N, customers]
            full_duration_matrix: Duration matrix [DEPOT, HUB_1, ..., HUB_N, customers]
            config: Configuration dictionary
        """
        self.orders = orders
        self.fleet = fleet
        self.depot = depot
        self.hub_config = multi_hub_config
        self.hub_manager = hub_routing_manager
        self.full_distance_matrix = full_distance_matrix
        self.full_duration_matrix = full_duration_matrix
        self.config = config or {}

        # Create index manager for dynamic matrix indexing
        hub_ids = multi_hub_config.get_all_hub_ids()
        self.index_manager = HubIndexManager(hub_ids)

        # Build hub_id to matrix index map
        self.hub_index_map = {
            hub_id: self.index_manager.get_hub_index(hub_id)
            for hub_id in hub_ids
        }

        # Build order_id to matrix index map
        self.order_index_map = {
            order.sale_order_id: self.index_manager.get_customer_index(i)
            for i, order in enumerate(orders)
        }

        # Classify orders by hub (with dynamic assignment if configured)
        self.classified_orders = self._classify_orders_smart()

        self._print_classification_summary()

    def _classify_orders_smart(self) -> Dict[str, List[Order]]:
        """
        Classify orders using configured source assignment mode.

        Supports:
        - zone_based: Traditional zone-based assignment
        - dynamic: Pure cost-based assignment
        - hybrid: Dynamic with zone-based fallback

        Returns:
            Dict mapping source_id to list of orders
        """
        source_assignment = self.hub_config.source_assignment

        if source_assignment.mode == "zone_based":
            # Use existing zone-based classification
            return self.hub_manager.classify_orders(self.orders)

        # For dynamic or hybrid modes, use DynamicSourceAssigner
        assigner = DynamicSourceAssigner(
            depot=self.depot,
            hub_configs=self.hub_config.hubs,
            distance_matrix=self.full_distance_matrix,
            duration_matrix=self.full_duration_matrix,
            config=source_assignment,
            hub_index_map=self.hub_index_map,
            order_index_offset=self.index_manager.customer_start_index,
        )

        # Get zone-based classification for hybrid fallback
        zone_assignments = self.hub_manager.classify_orders_zone_based(self.orders)

        # Apply dynamic/hybrid assignment
        result = assigner.assign_orders(self.orders, zone_assignments)

        # If dynamic assigner returns empty (mode=zone_based), use zone classification
        if not result or all(len(orders) == 0 for orders in result.values()):
            return zone_assignments

        # Log assignment summary
        summary = assigner.get_assignment_summary(self.orders, result)
        print(f"\n[Source Assignment] Mode: {source_assignment.mode}")
        print(f"  Threshold: {source_assignment.min_cost_advantage_percent}% cost advantage required to switch")

        return result

    def _print_classification_summary(self):
        """Print order classification summary."""
        print("\n[Multi-Hub VRP] Order Classification:")
        total_hub_orders = 0
        total_hub_weight = 0.0

        for source_id, source_orders in self.classified_orders.items():
            weight = sum(o.load_weight_in_kg for o in source_orders)
            if source_id == MultiHubRoutingManager.DIRECT_KEY:
                print(f"  DEPOT (direct): {len(source_orders)} orders, {weight:.1f} kg")
            else:
                hub_config = self.hub_config.get_hub_by_id(source_id)
                hub_name = hub_config.hub.name if hub_config else source_id
                mode = hub_config.blind_van_config.mode.value if hub_config else "unknown"
                print(f"  {hub_name} ({source_id}): {len(source_orders)} orders, {weight:.1f} kg [Mode: {mode}]")
                total_hub_orders += len(source_orders)
                total_hub_weight += weight

        print(f"  Total hub orders: {total_hub_orders}, Total hub weight: {total_hub_weight:.1f} kg")
        print(f"  Blind van return to depot: {self.hub_config.blind_van_return_to_depot}")

    def solve(
        self,
        optimization_strategy: str = "balanced",
        time_limit: int = 300,
    ) -> RoutingSolution:
        """
        Solve multi-hub routing problem.

        Args:
            optimization_strategy: Optimization strategy
            time_limit: Time limit in seconds (per tier)

        Returns:
            RoutingSolution combining all tiers
        """
        start_time = time_module.time()

        try:
            # Zero hub mode: Direct routing from DEPOT
            if self.hub_config.is_zero_hub_mode:
                print("\n[Zero Hub Mode] All orders routing directly from DEPOT")
                return self._solve_zero_hub_mode(optimization_strategy, time_limit)

            all_routes = []
            all_unassigned = []
            vehicle_counter = 0

            # Tier 1: Blind Van multi-hub tour
            print("\n[Tier 1] Solving Blind Van multi-hub consolidation...")
            tier1_routes = self._solve_tier1_blind_van_multi_hub(time_limit)
            all_routes.extend(tier1_routes)
            vehicle_counter += len(tier1_routes)

            # Tier 2: Motors from each hub and DEPOT
            print("\n[Tier 2] Solving Motor routes from each hub and DEPOT...")
            tier2_routes, tier2_unassigned = self._solve_tier2_all_sources(
                time_limit, vehicle_counter
            )
            all_routes.extend(tier2_routes)
            all_unassigned.extend(tier2_unassigned)

            computation_time = time_module.time() - start_time

            solution = RoutingSolution(
                routes=all_routes,
                unassigned_orders=all_unassigned,
                optimization_strategy=optimization_strategy,
                computation_time=computation_time,
            )

            print(f"\n[Multi-Hub Solution] {len(all_routes)} total routes, computation time: {computation_time:.2f}s")
            return solution

        except Exception as e:
            raise TwoTierRoutingError(f"Multi-hub routing failed: {str(e)}")

    def _solve_zero_hub_mode(
        self,
        optimization_strategy: str,
        time_limit: int
    ) -> RoutingSolution:
        """
        Solve with all orders directly from DEPOT (no hub routing).

        Args:
            optimization_strategy: Optimization strategy
            time_limit: Time limit in seconds

        Returns:
            RoutingSolution from single-tier VRP
        """
        # Extract depot-only matrix (remove hub rows/columns if any)
        # In zero-hub mode, matrix should be [DEPOT, customers...]
        # But we still use index manager in case config had hubs but enabled=false

        depot_idx = self.index_manager.get_depot_index()
        customer_indices = [
            self.index_manager.get_customer_index(i)
            for i in range(len(self.orders))
        ]
        all_indices = [depot_idx] + customer_indices

        distance_matrix = self._extract_submatrix(self.full_distance_matrix, all_indices)
        duration_matrix = self._extract_submatrix(self.full_duration_matrix, all_indices)

        # Check if multi-trip is enabled
        multi_trip_config = self.config.get("routing", {}).get("multi_trip", {})
        use_multi_trip = (
            multi_trip_config.get("enabled", False)
            and self.fleet.multiple_trips
        )

        if use_multi_trip:
            solver = MultiTripSolver(
                orders=self.orders,
                fleet=self.fleet,
                depot=self.depot,
                distance_matrix=distance_matrix,
                duration_matrix=duration_matrix,
                config=self.config,
            )
            solution = solver.solve(optimization_strategy, time_limit, source="DEPOT")
        else:
            solver = VRPSolver(
                orders=self.orders,
                fleet=self.fleet,
                depot=self.depot,
                distance_matrix=distance_matrix,
                duration_matrix=duration_matrix,
                config=self.config,
            )
            solution = solver.solve(optimization_strategy, time_limit)
            # Mark all routes as from DEPOT
            for route in solution.routes:
                route.source = "DEPOT"

        return solution

    def _solve_tier1_blind_van_multi_hub(self, time_limit: int) -> List[Route]:
        """
        Solve Tier 1: Blind Van visits all hubs with orders in optimal sequence.

        Uses BlindVanRouter to support per-hub modes:
        - Mode A: Consolidation only
        - Mode B: Consolidation + en-route delivery

        Args:
            time_limit: Time limit in seconds

        Returns:
            List with Blind Van route(s)
        """
        # Find hubs that have orders
        hubs_with_orders = [
            hub_id for hub_id in self.classified_orders.keys()
            if hub_id != MultiHubRoutingManager.DIRECT_KEY
        ]

        if not hubs_with_orders:
            print("[Tier 1] No hub orders, skipping Blind Van")
            return []

        blind_van = self._get_blind_van_vehicle()
        if not blind_van:
            print("[Tier 1] Warning: Blind Van not found in fleet, skipping consolidation")
            return []

        # Get active hub configs
        active_hub_configs = [
            self.hub_config.get_hub_by_id(hub_id)
            for hub_id in hubs_with_orders
            if self.hub_config.get_hub_by_id(hub_id) is not None
        ]

        # Use BlindVanRouter for intelligent routing with Mode A/B support
        router = BlindVanRouter(
            depot=self.depot,
            hub_configs=active_hub_configs,
            orders=self.orders,
            classified_orders=self.classified_orders,
            blind_van=blind_van,
            distance_matrix=self.full_distance_matrix,
            duration_matrix=self.full_duration_matrix,
            multi_hub_config=self.hub_config,
            hub_index_map=self.hub_index_map,
            order_index_map=self.order_index_map,
        )

        route = router.solve()
        if not route:
            print("[Tier 1] BlindVanRouter returned no route")
            return []

        # Get en-route delivered orders and remove from DEPOT pool
        delivered_en_route = router.get_delivered_orders()
        if delivered_en_route:
            print(f"[Tier 1] En-route deliveries: {len(delivered_en_route)} orders")
            # Remove delivered orders from DEPOT pool for Tier 2
            depot_orders = self.classified_orders.get(MultiHubRoutingManager.DIRECT_KEY, [])
            for order in delivered_en_route:
                if order in depot_orders:
                    depot_orders.remove(order)

        # Get route summary
        summary = router.get_route_summary(route)

        # Build log message
        hub_names = []
        for stop in route.stops:
            if stop.order.sale_order_id.startswith("HUB_CONSOLIDATION"):
                hub_id = stop.order.partner_id
                hub_config = self.hub_config.get_hub_by_id(hub_id)
                if hub_config:
                    hub_names.append(hub_config.hub.name)

        if self.hub_config.blind_van_return_to_depot:
            route_str = f"DEPOT -> {' -> '.join(hub_names)} -> DEPOT"
        else:
            route_str = f"DEPOT -> {' -> '.join(hub_names)} (end at last hub)"

        print(f"[Tier 1] Blind Van: {route_str}")
        print(f"[Tier 1]   Total stops: {summary['total_stops']} (deliveries: {summary['delivery_stops']}, hubs: {summary['hub_stops']})")
        print(f"[Tier 1]   Distance: {route.total_distance:.1f} km, Cost: Rp {route.total_cost:,.0f}")

        return [route]

    def _solve_hub_tsp(self, hub_ids: List[str]) -> List[str]:
        """
        Solve TSP to find optimal hub visit sequence using nearest neighbor heuristic.

        Args:
            hub_ids: List of hub IDs to visit

        Returns:
            Ordered list of hub IDs representing optimal visit sequence
        """
        if len(hub_ids) <= 1:
            return hub_ids

        # Simple nearest neighbor TSP
        visited = [False] * len(hub_ids)
        sequence = []
        current_matrix_idx = self.index_manager.get_depot_index()

        for _ in range(len(hub_ids)):
            min_dist = float('inf')
            next_hub_idx = -1

            for i, hub_id in enumerate(hub_ids):
                if visited[i]:
                    continue
                hub_matrix_idx = self.index_manager.get_hub_index(hub_id)
                dist = self.full_distance_matrix[current_matrix_idx, hub_matrix_idx]
                if dist < min_dist:
                    min_dist = dist
                    next_hub_idx = i

            if next_hub_idx >= 0:
                visited[next_hub_idx] = True
                sequence.append(hub_ids[next_hub_idx])
                current_matrix_idx = self.index_manager.get_hub_index(hub_ids[next_hub_idx])

        return sequence

    def _solve_tier2_all_sources(
        self,
        time_limit: int,
        vehicle_id_offset: int
    ) -> Tuple[List[Route], List[Order]]:
        """
        Solve Tier 2 motor routing from all sources (hubs and DEPOT).

        Args:
            time_limit: Time limit in seconds
            vehicle_id_offset: Starting vehicle ID offset

        Returns:
            Tuple of (routes, unassigned_orders)
        """
        all_routes = []
        all_unassigned = []

        # Allocate vehicles across all sources
        source_fleets = self._allocate_vehicles_to_sources()

        for source_id, source_orders in self.classified_orders.items():
            if not source_orders:
                continue

            source_fleet = source_fleets.get(source_id)
            if not source_fleet:
                print(f"[Tier 2] Warning: No fleet allocated for {source_id}")
                continue

            if source_id == MultiHubRoutingManager.DIRECT_KEY:
                # Direct orders from DEPOT
                print(f"\n[Tier 2-DEPOT] Solving {len(source_orders)} direct orders...")
                routes, unassigned = self._solve_tier2_from_depot(
                    source_orders, source_fleet, time_limit, vehicle_id_offset
                )
            else:
                # Orders from specific hub
                hub_config = self.hub_config.get_hub_by_id(source_id)
                hub_name = hub_config.hub.name if hub_config else source_id
                print(f"\n[Tier 2-{source_id}] Solving {len(source_orders)} orders from {hub_name}...")
                routes, unassigned = self._solve_tier2_from_hub(
                    source_id, source_orders, source_fleet, time_limit, vehicle_id_offset
                )

            all_routes.extend(routes)
            all_unassigned.extend(unassigned)
            vehicle_id_offset += len(routes)

        return all_routes, all_unassigned

    def _solve_tier2_from_hub(
        self,
        hub_id: str,
        orders: List[Order],
        fleet: VehicleFleet,
        time_limit: int,
        vehicle_offset: int
    ) -> Tuple[List[Route], List[Order]]:
        """
        Solve motor routing from a specific hub.

        Args:
            hub_id: Hub identifier
            orders: Orders to deliver from this hub
            fleet: Allocated fleet for this hub
            time_limit: Time limit in seconds
            vehicle_offset: Vehicle ID offset

        Returns:
            Tuple of (routes, unassigned_orders)
        """
        hub_config = self.hub_config.get_hub_by_id(hub_id)
        if not hub_config:
            print(f"[Tier 2] Error: Hub {hub_id} not found")
            return [], orders

        hub_matrix_idx = self.index_manager.get_hub_index(hub_id)

        # Build sub-matrix: [HUB, orders...]
        order_indices = []
        for order in orders:
            try:
                order_idx = self.orders.index(order)
                order_indices.append(self.index_manager.get_customer_index(order_idx))
            except ValueError:
                continue

        all_indices = [hub_matrix_idx] + order_indices

        distance_matrix = self._extract_submatrix(self.full_distance_matrix, all_indices)
        duration_matrix = self._extract_submatrix(self.full_duration_matrix, all_indices)

        # Check if multi-trip is enabled
        multi_trip_config = self.config.get("routing", {}).get("multi_trip", {})
        use_multi_trip = (
            multi_trip_config.get("enabled", False)
            and fleet.multiple_trips
        )

        try:
            if use_multi_trip:
                solver = MultiTripSolver(
                    orders=orders,
                    fleet=fleet,
                    depot=hub_config.hub,  # Use hub as depot
                    distance_matrix=distance_matrix,
                    duration_matrix=duration_matrix,
                    config=self.config,
                )
                solution = solver.solve("balanced", time_limit, source=hub_id)
                # Add hub prefix to vehicle names
                for route in solution.routes:
                    route.vehicle.name = f"{hub_id.upper()}-{route.vehicle.name}"
            else:
                solver = VRPSolver(
                    orders=orders,
                    fleet=fleet,
                    depot=hub_config.hub,  # Use hub as depot
                    distance_matrix=distance_matrix,
                    duration_matrix=duration_matrix,
                    vehicle_id_offset=vehicle_offset,
                    config=self.config,
                )
                solution = solver.solve("balanced", time_limit)
                # Mark routes as originating from this hub
                for route in solution.routes:
                    route.source = hub_id
                    route.vehicle.name = f"{hub_id.upper()}-{route.vehicle.name}"

            print(f"[Tier 2-{hub_id}] {len(solution.routes)} routes, {solution.total_orders_delivered} orders delivered")
            if solution.unassigned_orders:
                print(f"[Tier 2-{hub_id}] Warning: {len(solution.unassigned_orders)} unassigned orders")

            return solution.routes, solution.unassigned_orders

        except Exception as e:
            print(f"[Tier 2-{hub_id}] Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return [], orders

    def _solve_tier2_from_depot(
        self,
        orders: List[Order],
        fleet: VehicleFleet,
        time_limit: int,
        vehicle_offset: int
    ) -> Tuple[List[Route], List[Order]]:
        """
        Solve motor routing from DEPOT for direct orders.

        Args:
            orders: Direct orders to deliver from DEPOT
            fleet: Allocated fleet for DEPOT
            time_limit: Time limit in seconds
            vehicle_offset: Vehicle ID offset

        Returns:
            Tuple of (routes, unassigned_orders)
        """
        # Build sub-matrix: [DEPOT, orders...]
        order_indices = []
        for order in orders:
            try:
                order_idx = self.orders.index(order)
                order_indices.append(self.index_manager.get_customer_index(order_idx))
            except ValueError:
                continue

        all_indices = [self.index_manager.get_depot_index()] + order_indices

        distance_matrix = self._extract_submatrix(self.full_distance_matrix, all_indices)
        duration_matrix = self._extract_submatrix(self.full_duration_matrix, all_indices)

        # Check if multi-trip is enabled
        multi_trip_config = self.config.get("routing", {}).get("multi_trip", {})
        use_multi_trip = (
            multi_trip_config.get("enabled", False)
            and fleet.multiple_trips
        )

        try:
            if use_multi_trip:
                solver = MultiTripSolver(
                    orders=orders,
                    fleet=fleet,
                    depot=self.depot,
                    distance_matrix=distance_matrix,
                    duration_matrix=duration_matrix,
                    config=self.config,
                )
                solution = solver.solve("balanced", time_limit, source="DEPOT")
                # Add DEPOT prefix to vehicle names
                for route in solution.routes:
                    route.vehicle.name = f"DEPOT-{route.vehicle.name}"
            else:
                solver = VRPSolver(
                    orders=orders,
                    fleet=fleet,
                    depot=self.depot,
                    distance_matrix=distance_matrix,
                    duration_matrix=duration_matrix,
                    vehicle_id_offset=vehicle_offset,
                    config=self.config,
                )
                solution = solver.solve("balanced", time_limit)
                # Mark routes as from DEPOT
                for route in solution.routes:
                    route.source = "DEPOT"
                    route.vehicle.name = f"DEPOT-{route.vehicle.name}"

            print(f"[Tier 2-DEPOT] {len(solution.routes)} routes, {solution.total_orders_delivered} orders delivered")
            if solution.unassigned_orders:
                print(f"[Tier 2-DEPOT] Warning: {len(solution.unassigned_orders)} unassigned orders")

            return solution.routes, solution.unassigned_orders

        except Exception as e:
            print(f"[Tier 2-DEPOT] Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return [], orders

    def _allocate_vehicles_to_sources(self) -> Dict[str, VehicleFleet]:
        """
        Allocate vehicles proportionally across sources based on weight.

        Returns:
            Dict mapping source_id to VehicleFleet
        """
        from ..models.vehicle import VehicleFleet as VF

        # Calculate weights per source
        source_weights = {}
        total_weight = 0.0
        for source_id, orders in self.classified_orders.items():
            weight = sum(o.load_weight_in_kg for o in orders)
            source_weights[source_id] = weight
            total_weight += weight

        if total_weight == 0:
            return {}

        # Get motor vehicles (exclude Blind Van)
        motor_vehicles = [
            (v, count, unlimited)
            for v, count, unlimited in self.fleet.vehicle_types
            if v.name != self.hub_config.blind_van_vehicle_name
        ]

        print(f"\n[Vehicle Allocation] Total weight: {total_weight:.1f} kg across {len(source_weights)} sources")

        # Allocate proportionally
        allocations = {}
        for source_id, weight in source_weights.items():
            if not self.classified_orders.get(source_id):
                continue

            ratio = weight / total_weight if total_weight > 0 else 0
            source_allocation = []

            for vehicle, count, unlimited in motor_vehicles:
                if unlimited:
                    source_allocation.append((vehicle, 50, True))
                else:
                    allocated_count = max(1, round(count * ratio)) if weight > 0 else 0
                    if allocated_count > 0:
                        source_allocation.append((vehicle, allocated_count, False))

            if source_allocation:
                allocations[source_id] = VF(
                    vehicle_types=source_allocation,
                    return_to_depot=self.fleet.return_to_depot,
                    priority_time_tolerance=self.fleet.priority_time_tolerance,
                    non_priority_time_tolerance=self.fleet.non_priority_time_tolerance,
                    multiple_trips=self.fleet.multiple_trips,
                    relax_time_windows=getattr(self.fleet, 'relax_time_windows', False),
                    time_window_relaxation_minutes=getattr(self.fleet, 'time_window_relaxation_minutes', 0),
                )

                source_name = source_id if source_id == "DEPOT" else self.hub_config.get_hub_by_id(source_id).hub.name
                print(f"  {source_name}: {ratio*100:.1f}% ({weight:.1f} kg)")

        return allocations

    def _extract_submatrix(self, matrix: np.ndarray, indices: List[int]) -> np.ndarray:
        """
        Extract sub-matrix from full matrix using given indices.

        Args:
            matrix: Full distance/duration matrix
            indices: List of indices to extract

        Returns:
            Sub-matrix of shape (len(indices), len(indices))
        """
        n = len(indices)
        submatrix = np.zeros((n, n))
        for i, idx1 in enumerate(indices):
            for j, idx2 in enumerate(indices):
                submatrix[i, j] = matrix[idx1, idx2]
        return submatrix

    def _get_blind_van_vehicle(self) -> Optional[Vehicle]:
        """Get Blind Van vehicle from fleet."""
        for vehicle_type, count, unlimited in self.fleet.vehicle_types:
            if vehicle_type.name == self.hub_config.blind_van_vehicle_name:
                return vehicle_type
        return None

    def get_routing_summary(self) -> Dict:
        """Get hub routing classification summary."""
        return self.hub_manager.get_routing_summary(self.orders)


# Backward compatibility alias
TwoTierVRPSolver = MultiHubVRPSolver
