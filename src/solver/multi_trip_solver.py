"""
Multi-Trip VRP Solver.

Orchestrates solving VRP in multiple phases based on time window clusters,
then assigns physical vehicles across trips.
"""
import time as time_module
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from ..models.location import Depot
from ..models.order import Order
from ..models.route import Route, RoutingSolution
from ..models.vehicle import Vehicle, VehicleFleet
from ..utils.time_window_clustering import TimeWindowCluster, TimeWindowClusterer
from .vrp_solver import VRPSolver, VRPSolverError


@dataclass
class PhysicalVehicleAssignment:
    """Tracks a physical vehicle's assignments across trips."""

    physical_id: str  # e.g., "Motor_1"
    vehicle_type: str  # Base vehicle type name (e.g., "Sepeda Motor")
    source: str  # HUB or DEPOT
    trips: List[Route] = field(default_factory=list)
    last_end_time: int = 0  # When vehicle finishes last trip (minutes)

    @property
    def trip_count(self) -> int:
        return len(self.trips)


class MultiTripSolver:
    """
    Solver that handles multi-trip vehicle routing.

    Process:
    1. Cluster orders by time windows
    2. Solve each cluster independently with full fleet
    3. Post-process to assign physical vehicles across clusters
    4. Update trip numbers for continuity
    """

    def __init__(
        self,
        orders: List[Order],
        fleet: VehicleFleet,
        depot: Depot,
        distance_matrix: np.ndarray,
        duration_matrix: np.ndarray,
        config: dict = None,
    ):
        """
        Initialize MultiTripSolver.

        Args:
            orders: List of orders to deliver
            fleet: Vehicle fleet available
            depot: Depot/hub location (starting point)
            distance_matrix: Distance matrix in kilometers
            duration_matrix: Duration matrix in minutes
            config: Configuration dictionary
        """
        self.orders = orders
        self.fleet = fleet
        self.depot = depot
        self.distance_matrix = distance_matrix
        self.duration_matrix = duration_matrix
        self.config = config or {}

        # Multi-trip configuration
        multi_trip_config = self.config.get("routing", {}).get("multi_trip", {})
        self.enabled = multi_trip_config.get("enabled", True)
        self.buffer_minutes = multi_trip_config.get("buffer_minutes", 60)

        # Vehicle reuse config
        vehicle_reuse = multi_trip_config.get("vehicle_reuse", {})
        self.max_trips = vehicle_reuse.get("max_trips_per_vehicle", 3)
        self.same_source_only = vehicle_reuse.get("same_source_only", True)

        # Clustering config
        clustering_config = multi_trip_config.get("clustering", {})
        self.gap_threshold = clustering_config.get("gap_threshold_minutes", 60)
        self.min_cluster_size = clustering_config.get("min_cluster_size", 1)

        # Initialize clusterer
        self.clusterer = TimeWindowClusterer(
            gap_threshold_minutes=self.gap_threshold,
            min_cluster_size=self.min_cluster_size,
        )

    def solve(
        self,
        optimization_strategy: str = "balanced",
        time_limit: int = 300,
        source: str = "DEPOT",
    ) -> RoutingSolution:
        """
        Solve multi-trip VRP.

        Args:
            optimization_strategy: Optimization strategy for VRP
            time_limit: Time limit per cluster solve (seconds)
            source: Source location identifier (DEPOT or hub ID)

        Returns:
            RoutingSolution with multi-trip routes
        """
        start_time = time_module.time()

        if not self.orders:
            return RoutingSolution(
                routes=[],
                unassigned_orders=[],
                optimization_strategy=optimization_strategy,
                computation_time=0,
            )

        # Step 1: Cluster orders by time window
        clusters = self.clusterer.cluster_orders(self.orders)

        # If only one cluster or feature disabled, use single solve
        if not self.enabled or len(clusters) <= 1:
            print(f"[Multi-Trip] Single cluster detected, using standard solver")
            return self._single_solve(optimization_strategy, time_limit, source)

        print(
            f"\n[Multi-Trip] Clustered {len(self.orders)} orders "
            f"into {len(clusters)} time window clusters"
        )
        for cluster in clusters:
            print(f"  {cluster}")

        # Step 2: Solve each cluster independently
        cluster_solutions: List[Tuple[TimeWindowCluster, RoutingSolution]] = []
        time_per_cluster = max(30, time_limit // len(clusters))

        for cluster in clusters:
            print(f"\n[Multi-Trip] Solving cluster {cluster.cluster_id}...")
            solution = self._solve_cluster(
                cluster,
                optimization_strategy,
                time_per_cluster,
                source,
            )
            cluster_solutions.append((cluster, solution))
            print(
                f"  -> {len(solution.routes)} routes, "
                f"{len(solution.unassigned_orders)} unassigned"
            )

        # Step 3: Assign physical vehicles across clusters
        all_routes = self._assign_physical_vehicles(cluster_solutions, source)

        # Step 4: Collect unassigned orders from all clusters
        all_unassigned: List[Order] = []
        for _, solution in cluster_solutions:
            all_unassigned.extend(solution.unassigned_orders)

        computation_time = time_module.time() - start_time

        # Summary
        multi_trip_count = sum(1 for r in all_routes if r.trip_number > 1)
        print(
            f"\n[Multi-Trip] Completed: {len(all_routes)} total routes, "
            f"{multi_trip_count} are trip 2+, "
            f"{len(all_unassigned)} unassigned"
        )

        return RoutingSolution(
            routes=all_routes,
            unassigned_orders=all_unassigned,
            optimization_strategy=optimization_strategy,
            computation_time=computation_time,
        )

    def _solve_cluster(
        self,
        cluster: TimeWindowCluster,
        optimization_strategy: str,
        time_limit: int,
        source: str,
    ) -> RoutingSolution:
        """Solve a single cluster with full fleet available."""
        # Build order index mapping: cluster order index -> original order index
        order_index_map = {
            self.orders.index(order): i for i, order in enumerate(cluster.orders)
        }

        # Extract submatrix for cluster orders
        # Indices: 0 (depot) + cluster order indices in original matrix
        original_indices = [0] + [self.orders.index(o) + 1 for o in cluster.orders]
        sub_distance = self._extract_submatrix(self.distance_matrix, original_indices)
        sub_duration = self._extract_submatrix(self.duration_matrix, original_indices)

        solver = VRPSolver(
            orders=cluster.orders,
            fleet=self.fleet,
            depot=self.depot,
            distance_matrix=sub_distance,
            duration_matrix=sub_duration,
            config=self.config,
        )

        try:
            solution = solver.solve(optimization_strategy, time_limit)
            # Set source for all routes
            for route in solution.routes:
                route.source = source
            return solution
        except VRPSolverError as e:
            print(f"  [Multi-Trip] Cluster solve failed: {e}")
            return RoutingSolution(
                routes=[],
                unassigned_orders=cluster.orders,
                optimization_strategy=optimization_strategy,
                computation_time=0,
            )

    def _extract_submatrix(
        self, matrix: np.ndarray, indices: List[int]
    ) -> np.ndarray:
        """Extract submatrix for given indices."""
        n = len(indices)
        submatrix = np.zeros((n, n))
        for i, idx_i in enumerate(indices):
            for j, idx_j in enumerate(indices):
                submatrix[i, j] = matrix[idx_i, idx_j]
        return submatrix

    def _assign_physical_vehicles(
        self,
        cluster_solutions: List[Tuple[TimeWindowCluster, RoutingSolution]],
        source: str,
    ) -> List[Route]:
        """
        Assign physical vehicles across cluster solutions.

        Strategy:
        1. Process clusters in chronological order
        2. For each route in a cluster, try to reuse a vehicle from previous cluster
        3. If vehicle finished early enough (with buffer), assign same physical ID
        4. Update trip_number accordingly
        """
        # Sort by cluster time
        sorted_solutions = sorted(
            cluster_solutions, key=lambda x: x[0].earliest_start
        )

        # Track physical vehicle assignments by vehicle type
        physical_vehicles: Dict[str, PhysicalVehicleAssignment] = {}
        all_routes: List[Route] = []
        next_physical_id: Dict[str, int] = {}  # vehicle_type -> next ID

        for cluster, solution in sorted_solutions:
            for route in solution.routes:
                if route.num_stops == 0:
                    continue

                # Get vehicle type (base name without ID)
                vehicle_type = self._get_vehicle_type(route.vehicle.name)

                # Calculate route timing
                route_start_time = route.departure_time
                route_end_time = self._calculate_route_end_time(route)

                # Try to find available physical vehicle of same type
                assigned = self._find_available_vehicle(
                    physical_vehicles,
                    vehicle_type,
                    route_start_time,
                    source,
                )

                if assigned:
                    # Reuse existing physical vehicle
                    route.trip_number = assigned.trip_count + 1
                    route.vehicle = self._create_vehicle_with_id(
                        route.vehicle,
                        int(assigned.physical_id.split("_")[-1]),
                    )
                    assigned.trips.append(route)
                    assigned.last_end_time = route_end_time
                else:
                    # Create new physical vehicle
                    if vehicle_type not in next_physical_id:
                        next_physical_id[vehicle_type] = 1

                    new_id = next_physical_id[vehicle_type]
                    next_physical_id[vehicle_type] += 1

                    physical_id = f"{vehicle_type}_{new_id}"
                    route.vehicle = self._create_vehicle_with_id(route.vehicle, new_id)
                    route.trip_number = 1

                    physical_vehicles[physical_id] = PhysicalVehicleAssignment(
                        physical_id=physical_id,
                        vehicle_type=vehicle_type,
                        source=source,
                        trips=[route],
                        last_end_time=route_end_time,
                    )

                route.source = source
                all_routes.append(route)

        # Log summary of multi-trip assignments
        multi_trip_vehicles = [
            pv for pv in physical_vehicles.values() if pv.trip_count > 1
        ]
        if multi_trip_vehicles:
            print(f"\n[Multi-Trip] {len(multi_trip_vehicles)} vehicles doing multiple trips:")
            for pv in multi_trip_vehicles:
                trip_times = [
                    f"Trip {t.trip_number}: {t.departure_time // 60:02d}:{t.departure_time % 60:02d}"
                    for t in pv.trips
                ]
                print(f"  {pv.physical_id}: {', '.join(trip_times)}")

        return all_routes

    def _get_vehicle_type(self, vehicle_name: str) -> str:
        """Extract base vehicle type from vehicle name (remove trailing ID)."""
        # Handle cases like "Sepeda Motor_1" -> "Sepeda Motor"
        # or "Sepeda Motor" -> "Sepeda Motor"
        parts = vehicle_name.rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            return parts[0]
        return vehicle_name

    def _create_vehicle_with_id(self, vehicle: Vehicle, new_id: int) -> Vehicle:
        """Create a copy of vehicle with new ID."""
        return vehicle.clone_with_id(new_id)

    def _calculate_route_end_time(self, route: Route) -> int:
        """
        Calculate when a route ends (last stop departure + return time).

        Args:
            route: The route to calculate end time for.

        Returns:
            End time in minutes from midnight.
        """
        if not route.stops:
            return route.departure_time

        last_stop = route.stops[-1]

        # Estimate return time to depot
        # Use last stop departure + estimated return duration
        # For simplicity, estimate 30 minutes return (can be enhanced)
        estimated_return = 30

        return last_stop.departure_time + estimated_return

    def _find_available_vehicle(
        self,
        physical_vehicles: Dict[str, PhysicalVehicleAssignment],
        vehicle_type: str,
        route_start_time: int,
        source: str,
    ) -> Optional[PhysicalVehicleAssignment]:
        """
        Find an available physical vehicle for the route.

        Args:
            physical_vehicles: Currently tracked physical vehicles.
            vehicle_type: Type of vehicle needed.
            route_start_time: When the new route starts.
            source: Source location for this route.

        Returns:
            PhysicalVehicleAssignment if found, None otherwise.
        """
        candidates: List[Tuple[PhysicalVehicleAssignment, int]] = []

        for physical_id, assignment in physical_vehicles.items():
            # Check vehicle type matches
            if assignment.vehicle_type != vehicle_type:
                continue

            # Check source matches (if required)
            if self.same_source_only and assignment.source != source:
                continue

            # Check max trips not exceeded
            if assignment.trip_count >= self.max_trips:
                continue

            # Check timing: vehicle must finish before route starts (with buffer)
            available_time = assignment.last_end_time + self.buffer_minutes
            if available_time <= route_start_time:
                candidates.append((assignment, available_time))

        if not candidates:
            return None

        # Return vehicle that becomes available earliest (best utilization)
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]

    def _single_solve(
        self,
        optimization_strategy: str,
        time_limit: int,
        source: str,
    ) -> RoutingSolution:
        """Fallback to single VRP solve when clustering not needed."""
        solver = VRPSolver(
            orders=self.orders,
            fleet=self.fleet,
            depot=self.depot,
            distance_matrix=self.distance_matrix,
            duration_matrix=self.duration_matrix,
            config=self.config,
        )

        try:
            solution = solver.solve(optimization_strategy, time_limit)
            for route in solution.routes:
                route.source = source
            return solution
        except VRPSolverError as e:
            print(f"[Multi-Trip] Single solve failed: {e}")
            return RoutingSolution(
                routes=[],
                unassigned_orders=self.orders,
                optimization_strategy=optimization_strategy,
                computation_time=0,
            )
