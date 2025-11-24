"""
Two-Tier VRP Solver for Hub-based consolidation routing.

Tier 1: Blind Van consolidates bulk delivery to hub (DEPOT -> HUB -> DEPOT, 05:30-06:00)
Tier 2a: Motors from HUB serve hub-zone orders (HUB -> customers -> HUB, 06:00+)
Tier 2b: Motors from DEPOT serve direct-zone orders (DEPOT -> customers -> DEPOT, 06:00+)
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

    Tier 1: Blind Van delivers bulk to hub (DEPOT -> HUB -> DEPOT)
    Tier 2a: Motors from HUB for hub-zone orders (HUB -> customers -> HUB)
    Tier 2b: Motors from DEPOT for direct-zone orders (DEPOT -> customers -> DEPOT)

    This ensures optimal distribution where:
    - Blind Van makes one trip to consolidate goods at HUB
    - Hub-zone orders are served by motors starting from HUB
    - Direct-zone orders are served by motors starting from DEPOT
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

        Tier 1: Blind Van (DEPOT -> HUB -> DEPOT) - Consolidation only
        Tier 2a: Motors from HUB (HUB -> hub-zone customers -> HUB)
        Tier 2b: Motors from DEPOT (DEPOT -> direct-zone customers -> DEPOT)

        Args:
            optimization_strategy: Optimization strategy
            time_limit: Time limit in seconds (per tier)

        Returns:
            RoutingSolution combining all tiers
        """
        start_time = time_module.time()

        try:
            # Track vehicle counter across all tiers for unique vehicle IDs
            vehicle_counter = 0

            # Tier 1: Solve Blind Van consolidation to hub (DEPOT -> HUB -> DEPOT)
            print("\n[Tier 1] Solving Blind Van consolidation (DEPOT -> HUB -> DEPOT)...")
            tier1_routes = self._solve_tier1_blind_van(time_limit)
            vehicle_counter += len(tier1_routes)

            # Tier 2: Solve Motors from both HUB and DEPOT
            print("\n[Tier 2] Solving Motor routes from HUB and DEPOT...")
            tier2_routes, unassigned = self._solve_tier2_motor(time_limit, vehicle_counter)

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
        Solve Tier 1: Blind Van bulk delivery to HUB only (DEPOT -> HUB -> DEPOT).

        Blind Van makes ONE trip carrying bulk goods (total weight of all hub orders) to HUB.
        NO customer deliveries - customers are served by Tier 2a motors from HUB.

        Args:
            time_limit: Time limit in seconds

        Returns:
            List with single Blind Van route (DEPOT -> HUB -> DEPOT)
        """
        if not self.hub_orders:
            print("[Tier 1] No hub orders, skipping Blind Van")
            return []

        # Get Blind Van vehicle type
        blind_van = None
        for vehicle_type, count, unlimited in self.fleet.vehicle_types:
            if vehicle_type.name == "Blind Van":
                blind_van = vehicle_type
                break

        if not blind_van:
            raise TwoTierRoutingError("Blind Van not found in vehicle fleet")

        # Calculate total weight to deliver to HUB
        hub_weight = sum(o.load_weight_in_kg for o in self.hub_orders)

        # Create HUB consolidation order
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

        # Create single HUB stop
        hub_stop = RouteStop(
            order=hub_order,
            arrival_time=360,  # 06:00
            departure_time=360,
            distance_from_prev=self.full_distance_matrix[0, 1],  # DEPOT -> HUB
            cumulative_weight=hub_weight,
            sequence=0,
        )

        # Create Blind Van route: DEPOT -> HUB -> DEPOT
        blind_van_route = Route(
            vehicle=blind_van,
            stops=[hub_stop],
            total_distance=self.full_distance_matrix[0, 1] * 2,  # DEPOT->HUB + HUB->DEPOT
            total_cost=self.full_distance_matrix[0, 1] * 2 * blind_van.cost_per_km,
            departure_time=330,  # 05:30
            source="DEPOT",
            trip_number=1
        )

        print(f"[Tier 1] ✅ Blind Van: DEPOT -> HUB -> DEPOT")
        print(f"[Tier 1]   Distance: {blind_van_route.total_distance:.1f} km, Weight: {hub_weight:.1f} kg, Cost: Rp {blind_van_route.total_cost:,.0f}")

        return [blind_van_route]

    def _solve_tier2_motor(self, time_limit: int, vehicle_id_offset: int) -> Tuple[List[Route], List[Order]]:
        """
        Solve Tier 2: Motor distribution from BOTH HUB and DEPOT.

        Tier 2a: Motors from HUB for hub-zone orders (HUB → customers → HUB)
        Tier 2b: Motors from DEPOT for direct-zone orders (DEPOT → customers → DEPOT)

        Args:
            time_limit: Time limit in seconds
            vehicle_id_offset: Starting vehicle ID offset (continues from Tier 1)

        Returns:
            Tuple of (routes, unassigned_orders)
        """
        all_routes = []
        all_unassigned = []

        # Allocate vehicles smartly between HUB and DEPOT (ONCE - no duplication)
        print("\n[Vehicle Allocation] Splitting global vehicle pool...")
        hub_fleet, depot_fleet = self._allocate_vehicles_smartly()

        # Tier 2a: Motors from HUB for hub-zone orders
        print("\n[Tier 2a] Solving Motors from HUB for hub-zone customers...")
        tier2a_routes, tier2a_unassigned = self._solve_tier2a_hub(time_limit, vehicle_id_offset, hub_fleet)
        all_routes.extend(tier2a_routes)
        all_unassigned.extend(tier2a_unassigned)

        # Update offset for Tier 2b
        vehicle_id_offset += len(tier2a_routes)

        # Tier 2b: Motors from DEPOT for direct-zone orders
        print("\n[Tier 2b] Solving Motors from DEPOT for direct-zone customers...")
        tier2b_routes, tier2b_unassigned = self._solve_tier2b_depot(time_limit, vehicle_id_offset, depot_fleet)
        all_routes.extend(tier2b_routes)
        all_unassigned.extend(tier2b_unassigned)

        return all_routes, all_unassigned

    def _solve_tier2a_hub(self, time_limit: int, vehicle_id_offset: int, allocated_fleet: VehicleFleet) -> Tuple[List[Route], List[Order]]:
        """
        Solve Tier 2a: Motor distribution FROM HUB for hub-zone orders.

        Motors deliver hub-zone orders starting from HUB.
        Location indices: 0=HUB, 1+=hub-zone-customers

        Args:
            time_limit: Time limit in seconds
            vehicle_id_offset: Starting vehicle ID offset (continues from Tier 1)
            allocated_fleet: Pre-allocated fleet for HUB routes (from smart allocation)

        Returns:
            Tuple of (routes, unassigned_orders)
        """
        if not self.hub_orders:
            print("[Tier 2a] No hub-zone orders, Motors from HUB not needed")
            return [], []

        # Create distance matrix for hub-zone orders with HUB as depot
        # Get indices of hub-zone customers in full matrix
        hub_customer_indices = [i + 2 for i, order in enumerate(self.orders) if order in self.hub_orders]

        # Build custom distance matrix: [HUB, hub_customer_1, hub_customer_2, ...]
        # Map: HUB (index 1 in full matrix) becomes index 0 in tier2a matrix
        all_indices = [1] + hub_customer_indices
        n = len(all_indices)

        tier2a_distance_matrix = np.zeros((n, n))
        tier2a_duration_matrix = np.zeros((n, n))

        for i, idx1 in enumerate(all_indices):
            for j, idx2 in enumerate(all_indices):
                tier2a_distance_matrix[i, j] = self.full_distance_matrix[idx1, idx2]
                tier2a_duration_matrix[i, j] = self.full_duration_matrix[idx1, idx2]

        # Solve with hub-zone orders, using HUB as depot
        try:
            solver = VRPSolver(
                orders=self.hub_orders,  # Hub-zone orders
                fleet=allocated_fleet,  # Use allocated fleet from smart allocation
                depot=self.hub,  # Use HUB as depot
                distance_matrix=tier2a_distance_matrix,
                duration_matrix=tier2a_duration_matrix,
                vehicle_id_offset=vehicle_id_offset,  # Pass offset for unique IDs
            )

            solution = solver.solve(
                optimization_strategy="balanced",
                time_limit=time_limit,
            )

            # Set source to HUB and add HUB- prefix to vehicle names
            for route in solution.routes:
                route.source = "HUB"
                route.trip_number = 1
                route.vehicle.name = f"HUB-{route.vehicle.name}"

            print(f"[Tier 2a] ✅ {len(solution.routes)} Motor routes from HUB created")
            print(f"[Tier 2a]   Delivered: {solution.total_orders_delivered} hub-zone orders")
            if solution.unassigned_orders:
                print(f"[Tier 2a]   ⚠️ Unassigned: {len(solution.unassigned_orders)} orders")

            return solution.routes, solution.unassigned_orders

        except Exception as e:
            print(f"[Tier 2a] Error solving Motors from HUB: {str(e)}")
            import traceback
            traceback.print_exc()
            return [], []

    def _solve_tier2b_depot(self, time_limit: int, vehicle_id_offset: int, allocated_fleet: VehicleFleet) -> Tuple[List[Route], List[Order]]:
        """
        Solve Tier 2b: Motor distribution FROM DEPOT for direct-zone orders.

        Motors deliver direct-zone orders starting from DEPOT.
        Location indices: 0=DEPOT, 1+=direct-zone-customers

        Args:
            time_limit: Time limit in seconds
            vehicle_id_offset: Starting vehicle ID offset (continues from Tier 2a)
            allocated_fleet: Pre-allocated fleet for DEPOT routes (from smart allocation)

        Returns:
            Tuple of (routes, unassigned_orders)
        """
        if not self.direct_orders:
            print("[Tier 2b] No direct-zone orders, Motors from DEPOT not needed")
            return [], []

        # Create distance matrix for direct-zone orders with DEPOT as depot
        # Get indices of direct-zone customers in full matrix
        direct_customer_indices = [i + 2 for i, order in enumerate(self.orders) if order in self.direct_orders]

        # Build custom distance matrix: [DEPOT, direct_customer_1, direct_customer_2, ...]
        all_indices = [0] + direct_customer_indices
        n = len(all_indices)

        tier2b_distance_matrix = np.zeros((n, n))
        tier2b_duration_matrix = np.zeros((n, n))

        for i, idx1 in enumerate(all_indices):
            for j, idx2 in enumerate(all_indices):
                tier2b_distance_matrix[i, j] = self.full_distance_matrix[idx1, idx2]
                tier2b_duration_matrix[i, j] = self.full_duration_matrix[idx1, idx2]

        # Solve with direct-zone orders, using DEPOT as depot
        try:
            solver = VRPSolver(
                orders=self.direct_orders,  # Direct-zone orders
                fleet=allocated_fleet,  # Use allocated fleet from smart allocation
                depot=self.depot,  # Use DEPOT as depot
                distance_matrix=tier2b_distance_matrix,
                duration_matrix=tier2b_duration_matrix,
                vehicle_id_offset=vehicle_id_offset,  # Pass offset for unique IDs
            )

            solution = solver.solve(
                optimization_strategy="balanced",
                time_limit=time_limit,
            )

            # Set source to DEPOT and add DEPOT- prefix to vehicle names
            for route in solution.routes:
                route.source = "DEPOT"
                route.trip_number = 1
                route.vehicle.name = f"DEPOT-{route.vehicle.name}"

            print(f"[Tier 2b] ✅ {len(solution.routes)} Motor routes from DEPOT created")
            print(f"[Tier 2b]   Delivered: {solution.total_orders_delivered} direct-zone orders")
            if solution.unassigned_orders:
                print(f"[Tier 2b]   ⚠️ Unassigned: {len(solution.unassigned_orders)} orders")

            return solution.routes, solution.unassigned_orders

        except Exception as e:
            print(f"[Tier 2b] Error solving Motors from DEPOT: {str(e)}")
            import traceback
            traceback.print_exc()
            return [], []

    def _allocate_vehicles_smartly(self) -> Tuple[VehicleFleet, VehicleFleet]:
        """
        Intelligently allocate global vehicle pool between HUB and DEPOT.

        Splits vehicles proportionally based on weight, with smart matching:
        - Larger capacity vehicles → zones with heavier demand
        - Unlimited vehicles (motors) → split proportionally by weight

        Returns:
            Tuple of (hub_fleet, depot_fleet) with allocated vehicles
        """
        from ..models.vehicle import VehicleFleet as VF

        # Calculate weight ratio
        hub_weight = sum(o.load_weight_in_kg for o in self.hub_orders) if self.hub_orders else 0
        direct_weight = sum(o.load_weight_in_kg for o in self.direct_orders) if self.direct_orders else 0
        total_weight = hub_weight + direct_weight

        if total_weight == 0:
            raise TwoTierRoutingError("No orders to route")

        hub_ratio = hub_weight / total_weight
        depot_ratio = direct_weight / total_weight

        print(f"[Vehicle Allocation] HUB: {hub_weight:.1f}kg ({hub_ratio*100:.1f}%), DEPOT: {direct_weight:.1f}kg ({depot_ratio*100:.1f}%)")

        # Get motor vehicles (exclude Blind Van)
        motor_vehicles = [(v, count, unlimited) for v, count, unlimited in self.fleet.vehicle_types if v.name != "Blind Van"]

        if not motor_vehicles:
            raise TwoTierRoutingError("No motor vehicles found in fleet")

        # Separate fixed and unlimited vehicles
        fixed_vehicles = [(v, count) for v, count, unlimited in motor_vehicles if not unlimited]
        unlimited_vehicles = [(v, count) for v, count, unlimited in motor_vehicles if unlimited]

        # Sort fixed vehicles by capacity (largest first) for smart allocation
        fixed_vehicles.sort(key=lambda x: x[0].capacity, reverse=True)

        hub_allocation = []
        depot_allocation = []

        # Smart allocation of fixed vehicles
        for vehicle_type, total_count in fixed_vehicles:
            # If only one zone has orders, allocate all to that zone
            if hub_weight == 0:
                depot_allocation.append((vehicle_type, total_count, False))
                print(f"[Vehicle Allocation]   {vehicle_type.name}: 0 → HUB, {total_count} → DEPOT (no HUB demand)")
            elif direct_weight == 0:
                hub_allocation.append((vehicle_type, total_count, False))
                print(f"[Vehicle Allocation]   {vehicle_type.name}: {total_count} → HUB, 0 → DEPOT (no DEPOT demand)")
            else:
                # Calculate proportional split
                hub_count = round(total_count * hub_ratio)
                depot_count = total_count - hub_count

                # Ensure at least one vehicle for each zone if possible and needed
                if hub_count == 0 and total_count > 0 and hub_weight > 0:
                    hub_count = 1
                    depot_count = total_count - 1
                elif depot_count == 0 and total_count > 0 and direct_weight > 0:
                    depot_count = 1
                    hub_count = total_count - 1

                if hub_count > 0:
                    hub_allocation.append((vehicle_type, hub_count, False))
                if depot_count > 0:
                    depot_allocation.append((vehicle_type, depot_count, False))

                print(f"[Vehicle Allocation]   {vehicle_type.name}: {hub_count} → HUB, {depot_count} → DEPOT")

        # Allocate unlimited vehicles proportionally
        for vehicle_type, _ in unlimited_vehicles:
            # Unlimited vehicles are available to both zones
            hub_allocation.append((vehicle_type, 50, True))  # Keep unlimited flag
            depot_allocation.append((vehicle_type, 50, True))
            print(f"[Vehicle Allocation]   {vehicle_type.name}: unlimited → HUB, unlimited → DEPOT")

        # Create fleets with allocated vehicles
        if not hub_allocation:
            hub_allocation = [(fixed_vehicles[0][0], 0, False)] if fixed_vehicles else []
        if not depot_allocation:
            depot_allocation = [(fixed_vehicles[0][0], 0, False)] if fixed_vehicles else []

        hub_fleet = VF(
            vehicle_types=hub_allocation,
            return_to_depot=self.fleet.return_to_depot,
            priority_time_tolerance=self.fleet.priority_time_tolerance,
            non_priority_time_tolerance=self.fleet.non_priority_time_tolerance,
            multiple_trips=self.fleet.multiple_trips,
            relax_time_windows=self.fleet.relax_time_windows,
            time_window_relaxation_minutes=self.fleet.time_window_relaxation_minutes,
        )

        depot_fleet = VF(
            vehicle_types=depot_allocation,
            return_to_depot=self.fleet.return_to_depot,
            priority_time_tolerance=self.fleet.priority_time_tolerance,
            non_priority_time_tolerance=self.fleet.non_priority_time_tolerance,
            multiple_trips=self.fleet.multiple_trips,
            relax_time_windows=self.fleet.relax_time_windows,
            time_window_relaxation_minutes=self.fleet.time_window_relaxation_minutes,
        )

        return hub_fleet, depot_fleet

    def get_routing_summary(self) -> Dict:
        """Get hub routing classification summary."""
        return self.hub_manager.get_hub_routing_summary(self.orders)
