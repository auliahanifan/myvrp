"""
Two-Tier VRP Solver for Hub-based consolidation routing.

Tier 1: Blind Van consolidates hub-zone orders (DEPOT -> HUB -> DEPOT, 05:30-06:00)
Tier 2: Sepeda Motor distributes from DEPOT & HUB (06:00+)
"""
from typing import List, Tuple, Optional, Dict
import numpy as np
import time as time_module

from ..models.order import Order
from ..models.vehicle import VehicleFleet, Vehicle
from ..models.location import Depot, Hub, Location
from ..models.route import Route, RouteStop, RoutingSolution
from ..utils.hub_routing import HubRoutingManager
from .vrp_solver import VRPSolver


class TwoTierRoutingError(Exception):
    """Custom exception for two-tier routing errors."""
    pass


class TwoTierVRPSolver:
    """
    Two-tier routing solver for hub-based consolidation.

    Tier 1: Blind Van consolidates hub-zone orders (DEPOT -> HUB -> DEPOT)
    Tier 2: Sepeda Motor distributes from DEPOT (direct-zone) and HUB (hub-zone)
    """

    def __init__(
        self,
        orders: List[Order],
        fleet: VehicleFleet,
        depot: Depot,
        hub: Hub,
        hub_manager: HubRoutingManager,
        full_distance_matrix: np.ndarray,  # [DEPOT, HUB, all_customers]
        full_duration_matrix: np.ndarray,
    ):
        """
        Initialize two-tier VRP solver.

        Args:
            orders: List of all orders
            fleet: Vehicle fleet (must have Blind Van and Sepeda Motor)
            depot: Main depot location
            hub: Hub location
            hub_manager: HubRoutingManager for order classification
            full_distance_matrix: Distance matrix [DEPOT(0), HUB(1), customers(2+)]
            full_duration_matrix: Duration matrix [DEPOT(0), HUB(1), customers(2+)]
        """
        self.orders = orders
        self.fleet = fleet
        self.depot = depot
        self.hub = hub
        self.hub_manager = hub_manager
        self.full_distance_matrix = full_distance_matrix
        self.full_duration_matrix = full_duration_matrix

        # Classify orders
        self.hub_orders, self.direct_orders = hub_manager.classify_orders(orders)

        print(f"[Two-Tier VRP] Hub orders: {len(self.hub_orders)}, Direct orders: {len(self.direct_orders)}")
        print(f"[Two-Tier VRP] Hub weight: {sum(o.load_weight_in_kg for o in self.hub_orders):.1f} kg")
        print(f"[Two-Tier VRP] Direct weight: {sum(o.load_weight_in_kg for o in self.direct_orders):.1f} kg")

    def solve(
        self,
        optimization_strategy: str = "balanced",
        time_limit: int = 300,
    ) -> RoutingSolution:
        """
        Solve two-tier routing problem.

        Tier 1: Blind Van (DEPOT -> HUB -> hub-zone customers -> DEPOT)
        Tier 2: Motor (DEPOT -> direct-zone customers -> DEPOT)

        Args:
            optimization_strategy: Optimization strategy
            time_limit: Time limit in seconds (per tier)

        Returns:
            RoutingSolution combining both tiers
        """
        start_time = time_module.time()

        try:
            # Tier 1: Solve Blind Van consolidation + delivery (DEPOT -> HUB -> customers)
            print("\n[Tier 1] Solving Blind Van (DEPOT -> HUB -> hub-zone customers -> DEPOT)...")
            tier1_routes = self._solve_tier1_blind_van(time_limit)

            # Tier 2: Solve Motor for direct-zone ONLY (DEPOT -> direct customers)
            print("\n[Tier 2] Solving Motor for direct-zone customers...")
            tier2_routes, unassigned = self._solve_tier2_motor(time_limit)

            # Combine solutions
            all_routes = tier1_routes + tier2_routes
            computation_time = time_module.time() - start_time

            solution = RoutingSolution(
                routes=all_routes,
                unassigned_orders=unassigned,
                optimization_strategy=optimization_strategy,
                computation_time=computation_time,
            )

            print(f"\n[Two-Tier Solution] {len(all_routes)} total routes, computation time: {computation_time:.2f}s")
            return solution

        except Exception as e:
            raise TwoTierRoutingError(f"Two-tier routing failed: {str(e)}")

    def _solve_tier1_blind_van(self, time_limit: int) -> List[Route]:
        """
        Solve Tier 1: Blind Van consolidation + delivery (DEPOT -> HUB -> hub-zone customers -> DEPOT).

        Blind Van picks up hub-zone orders, consolidates at HUB, then delivers them.
        Distance matrix for VRPSolver: [DEPOT, hub-zone-customers] (HUB is added manually after solving)

        Args:
            time_limit: Time limit in seconds

        Returns:
            List of routes (Blind Van route with hub consolidation + customer deliveries)
        """
        if not self.hub_orders:
            print("[Tier 1] No hub orders, skipping Blind Van")
            return []

        # Create distance matrix for Tier 1 (DEPOT + hub-zone customers only, NOT HUB)
        # VRPSolver expects: [DEPOT, customer_1, customer_2, ...]
        # Original full matrix: [DEPOT(0), HUB(1), all-customers(2+)]
        # We need to extract: [DEPOT(0), hub-customers]

        # Get indices of hub-zone customers in full matrix
        hub_customer_indices = [i + 2 for i, order in enumerate(self.orders) if order in self.hub_orders]

        # Build custom distance matrix: [DEPOT, hub_customer_1, hub_customer_2, ...]
        # Note: HUB is NOT included here - it will be added manually after solving
        all_indices = [0] + hub_customer_indices
        n = len(all_indices)

        tier1_distance_matrix = np.zeros((n, n))
        tier1_duration_matrix = np.zeros((n, n))

        for i, idx1 in enumerate(all_indices):
            for j, idx2 in enumerate(all_indices):
                tier1_distance_matrix[i, j] = self.full_distance_matrix[idx1, idx2]
                tier1_duration_matrix[i, j] = self.full_duration_matrix[idx1, idx2]

        # Create vehicle fleet with only Blind Van
        blind_van = None
        for vehicle_type, count, unlimited in self.fleet.vehicle_types:
            if vehicle_type.name == "Blind Van":
                blind_van = vehicle_type
                break

        if not blind_van:
            raise TwoTierRoutingError("Blind Van not found in vehicle fleet")

        # Create minimal fleet with just Blind Van
        from ..models.vehicle import VehicleFleet as VF
        blind_van_fleet = VF(
            vehicle_types=[(blind_van, 1, False)],
            return_to_depot=True,
            priority_time_tolerance=self.fleet.priority_time_tolerance,
            non_priority_time_tolerance=self.fleet.non_priority_time_tolerance,
            multiple_trips=False,
            relax_time_windows=False,
        )

        # Solve with hub-zone orders
        try:
            solver = VRPSolver(
                orders=self.hub_orders,  # Only hub-zone orders
                fleet=blind_van_fleet,
                depot=self.depot,
                distance_matrix=tier1_distance_matrix,
                duration_matrix=tier1_duration_matrix,
            )

            solution = solver.solve(
                optimization_strategy="minimize_cost",
                time_limit=time_limit,
            )

            # Get routes from solution
            if solution.routes:
                tier1_routes = solution.routes

                for route in tier1_routes:
                    # Create a HUB consolidation stop at the beginning
                    hub_weight = sum(o.load_weight_in_kg for o in self.hub_orders)

                    # Insert HUB stop at the beginning
                    hub_order = Order(
                        sale_order_id="HUB_CONSOLIDATION",
                        delivery_date=self.hub_orders[0].delivery_date,
                        delivery_time="05:30-06:00",
                        load_weight_in_kg=hub_weight,
                        partner_id="HUB",
                        display_name="Hub Consolidation",
                        alamat=self.hub.address,
                        coordinates=self.hub.coordinates,
                        kota="HUB",
                        is_priority=False,
                    )

                    hub_stop = RouteStop(
                        order=hub_order,
                        arrival_time=360,  # 06:00
                        departure_time=360,
                        distance_from_prev=self.full_distance_matrix[0, 1],
                        cumulative_weight=hub_weight,
                        sequence=0,
                    )

                    # Update existing stops to have correct sequence numbers and cumulative weights
                    all_stops = [hub_stop] + route.stops
                    route.stops = []
                    for i, stop in enumerate(all_stops):
                        stop.sequence = i
                        route.add_stop(stop)

                    # Calculate total distance including HUB
                    # DEPOT -> HUB + HUB -> customers + customers -> DEPOT
                    route.total_distance = self.full_distance_matrix[0, 1] + sum(s.distance_from_prev for s in route.stops[1:]) + self.full_distance_matrix[hub_customer_indices[-1], 0]
                    route.departure_time = 330  # 05:30

                print(f"[Tier 1] ✅ Blind Van: DEPOT -> HUB -> {len(self.hub_orders)} customers -> DEPOT")
                for route in tier1_routes:
                    print(f"[Tier 1]   Distance: {route.total_distance:.1f} km, Weight: {route.total_weight:.1f} kg, Stops: {route.num_stops}")

                return tier1_routes

            return []

        except Exception as e:
            print(f"[Tier 1] Warning: Could not create Blind Van route: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def _solve_tier2_motor(self, time_limit: int) -> Tuple[List[Route], List[Order]]:
        """
        Solve Tier 2: Motor distribution for DIRECT-ZONE ONLY.

        Motor delivers ONLY direct-zone orders from DEPOT.
        Hub-zone orders are delivered by Blind Van in Tier 1.

        Location indices: 0=DEPOT, 1+=direct-zone-customers

        Args:
            time_limit: Time limit in seconds

        Returns:
            Tuple of (routes, unassigned_orders)
        """
        if not self.direct_orders:
            print("[Tier 2] No direct-zone orders, Motor not needed")
            return [], []

        # Create distance matrix for direct-zone orders ONLY
        # Get indices of direct-zone customers in full matrix
        direct_customer_indices = [i + 2 for i, order in enumerate(self.orders) if order in self.direct_orders]

        # Build custom distance matrix: [DEPOT, direct_customer_1, direct_customer_2, ...]
        all_indices = [0] + direct_customer_indices
        n = len(all_indices)

        tier2_distance_matrix = np.zeros((n, n))
        tier2_duration_matrix = np.zeros((n, n))

        for i, idx1 in enumerate(all_indices):
            for j, idx2 in enumerate(all_indices):
                tier2_distance_matrix[i, j] = self.full_distance_matrix[idx1, idx2]
                tier2_duration_matrix[i, j] = self.full_duration_matrix[idx1, idx2]

        # Create motor-only fleet (exclude Blind Van)
        motor_fleet = self._create_motor_only_fleet()

        # Solve with ONLY direct-zone orders and Motor vehicles
        try:
            solver = VRPSolver(
                orders=self.direct_orders,  # Only direct-zone orders
                fleet=motor_fleet,  # Motor vehicles only (no Blind Van)
                depot=self.depot,
                distance_matrix=tier2_distance_matrix,
                duration_matrix=tier2_duration_matrix,
            )

            solution = solver.solve(
                optimization_strategy="balanced",
                time_limit=time_limit,
            )

            print(f"[Tier 2] ✅ {len(solution.routes)} Motor routes created")
            print(f"[Tier 2]   Delivered: {solution.total_orders_delivered} direct-zone orders")
            if solution.unassigned_orders:
                print(f"[Tier 2]   ⚠️ Unassigned: {len(solution.unassigned_orders)} orders")

            return solution.routes, solution.unassigned_orders

        except Exception as e:
            print(f"[Tier 2] Error solving Motor distribution: {str(e)}")
            raise

    def _create_motor_only_fleet(self):
        """
        Create a vehicle fleet with ONLY Motor vehicles (exclude Blind Van).

        This ensures Blind Van is only used in Tier 1 for consolidation,
        and Tier 2 only uses Motor vehicles for customer delivery.

        Returns:
            VehicleFleet with only Motor vehicles
        """
        from ..models.vehicle import VehicleFleet as VF

        # Filter out Blind Van, keep only Motor vehicles
        motor_vehicles = []
        for vehicle_type, count, unlimited in self.fleet.vehicle_types:
            if vehicle_type.name != "Blind Van":
                motor_vehicles.append((vehicle_type, count, unlimited))

        if not motor_vehicles:
            raise TwoTierRoutingError("No Motor vehicles found in fleet (Blind Van excluded)")

        motor_fleet = VF(
            vehicle_types=motor_vehicles,
            return_to_depot=self.fleet.return_to_depot,
            priority_time_tolerance=self.fleet.priority_time_tolerance,
            non_priority_time_tolerance=self.fleet.non_priority_time_tolerance,
            multiple_trips=self.fleet.multiple_trips,
            relax_time_windows=self.fleet.relax_time_windows,
            time_window_relaxation_minutes=self.fleet.time_window_relaxation_minutes,
        )

        print(f"[Tier 2] Motor-only fleet: {[v[0].name for v in motor_vehicles]}")
        return motor_fleet

    def get_routing_summary(self) -> Dict:
        """Get hub routing classification summary."""
        return self.hub_manager.get_hub_routing_summary(self.orders)
