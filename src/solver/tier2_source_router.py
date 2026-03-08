from dataclasses import dataclass, field
from typing import List

from ..models.location import Location
from ..models.order import Order
from ..models.route import Route, RoutingSolution
from ..models.vehicle import VehicleFleet
from ..utils.hub_routing import MultiHubRoutingManager
from .matrix_slicer import MatrixSlicer
from .multi_trip_solver import MultiTripSolver
from .order_classifier import ClassificationResult
from .solver_context import SolverContext
from .vrp_solver import VRPSolver


@dataclass
class SourceExecutionRequest:
    source_id: str
    source_label: str
    origin_location: Location
    orders: List[Order]
    fleet: VehicleFleet
    vehicle_id_offset: int
    optimization_strategy: str
    time_limit: int
    matrix_indices: List[int]
    route_name_prefix: str
    route_source_value: str


@dataclass
class Tier2Result:
    routes: List[Route]
    unassigned_orders: List[Order]
    next_vehicle_offset: int
    log_lines: List[str] = field(default_factory=list)


class Tier2SourceRouter:
    def solve_zero_hub(
        self,
        context: SolverContext,
        optimization_strategy: str,
        time_limit: int,
    ) -> RoutingSolution:
        slicer = MatrixSlicer(context)
        indices = slicer.get_depot_indices(context.orders)
        distance_matrix = slicer.extract(context.full_distance_matrix, indices)
        duration_matrix = slicer.extract(context.full_duration_matrix, indices)

        if self._use_multi_trip(context.fleet, context.config):
            solver = MultiTripSolver(
                orders=context.orders,
                fleet=context.fleet,
                depot=context.depot,
                distance_matrix=distance_matrix,
                duration_matrix=duration_matrix,
                config=context.config,
            )
            solution = solver.solve(optimization_strategy, time_limit, source="DEPOT")
        else:
            solver = VRPSolver(
                orders=context.orders,
                fleet=context.fleet,
                depot=context.depot,
                distance_matrix=distance_matrix,
                duration_matrix=duration_matrix,
                config=context.config,
            )
            solution = solver.solve(optimization_strategy, time_limit)
            for route in solution.routes:
                route.source = "DEPOT"

        return solution

    def solve_all_sources(
        self,
        context: SolverContext,
        classification: ClassificationResult,
        allocated_fleets: dict[str, VehicleFleet],
        optimization_strategy: str,
        time_limit: int,
        vehicle_offset: int,
    ) -> Tier2Result:
        all_routes: List[Route] = []
        all_unassigned: List[Order] = []
        log_lines: List[str] = []
        next_vehicle_offset = vehicle_offset

        for source_id, source_orders in classification.orders_by_source.items():
            if not source_orders:
                continue

            source_fleet = allocated_fleets.get(source_id)
            if not source_fleet:
                log_lines.append(f"[Tier 2] Warning: No fleet allocated for {source_id}")
                continue

            request = self._build_request(
                context=context,
                source_id=source_id,
                orders=source_orders,
                fleet=source_fleet,
                optimization_strategy=optimization_strategy,
                time_limit=time_limit,
                vehicle_offset=next_vehicle_offset,
            )
            routes, unassigned, request_logs = self._solve_request(context, request)
            all_routes.extend(routes)
            all_unassigned.extend(unassigned)
            log_lines.extend(request_logs)
            next_vehicle_offset += len(routes)

        return Tier2Result(
            routes=all_routes,
            unassigned_orders=all_unassigned,
            next_vehicle_offset=next_vehicle_offset,
            log_lines=log_lines,
        )

    def _build_request(
        self,
        context: SolverContext,
        source_id: str,
        orders: List[Order],
        fleet: VehicleFleet,
        optimization_strategy: str,
        time_limit: int,
        vehicle_offset: int,
    ) -> SourceExecutionRequest:
        slicer = MatrixSlicer(context)

        if source_id == MultiHubRoutingManager.DIRECT_KEY:
            return SourceExecutionRequest(
                source_id=source_id,
                source_label="DEPOT",
                origin_location=context.depot,
                orders=orders,
                fleet=fleet,
                vehicle_id_offset=vehicle_offset,
                optimization_strategy=optimization_strategy,
                time_limit=time_limit,
                matrix_indices=slicer.get_depot_indices(orders),
                route_name_prefix="DEPOT-",
                route_source_value="DEPOT",
            )

        hub_config = context.multi_hub_config.get_hub_by_id(source_id)
        if hub_config is None:
            raise ValueError(f"Hub {source_id} not found")

        return SourceExecutionRequest(
            source_id=source_id,
            source_label=hub_config.hub.name,
            origin_location=hub_config.hub,
            orders=orders,
            fleet=fleet,
            vehicle_id_offset=vehicle_offset,
            optimization_strategy=optimization_strategy,
            time_limit=time_limit,
            matrix_indices=slicer.get_hub_indices(source_id, orders),
            route_name_prefix=f"{source_id.upper()}-",
            route_source_value=source_id,
        )

    def _solve_request(
        self,
        context: SolverContext,
        request: SourceExecutionRequest,
    ) -> tuple[List[Route], List[Order], List[str]]:
        slicer = MatrixSlicer(context)
        distance_matrix = slicer.extract(context.full_distance_matrix, request.matrix_indices)
        duration_matrix = slicer.extract(context.full_duration_matrix, request.matrix_indices)

        try:
            if self._use_multi_trip(request.fleet, context.config):
                solver = MultiTripSolver(
                    orders=request.orders,
                    fleet=request.fleet,
                    depot=request.origin_location,
                    distance_matrix=distance_matrix,
                    duration_matrix=duration_matrix,
                    config=context.config,
                )
                solution = solver.solve(
                    request.optimization_strategy,
                    request.time_limit,
                    source=request.route_source_value,
                )
            else:
                solver = VRPSolver(
                    orders=request.orders,
                    fleet=request.fleet,
                    depot=request.origin_location,
                    distance_matrix=distance_matrix,
                    duration_matrix=duration_matrix,
                    vehicle_id_offset=request.vehicle_id_offset,
                    config=context.config,
                )
                solution = solver.solve(
                    request.optimization_strategy,
                    request.time_limit,
                )

            for route in solution.routes:
                route.source = request.route_source_value
                route.vehicle.name = f"{request.route_name_prefix}{route.vehicle.name}"

            return (
                solution.routes,
                solution.unassigned_orders,
                [
                    f"[Tier 2-{request.source_id}] {len(solution.routes)} routes, "
                    f"{solution.total_orders_delivered} orders delivered"
                ],
            )
        except Exception as exc:
            return [], request.orders, [f"[Tier 2-{request.source_id}] Error: {exc}"]

    def _use_multi_trip(self, fleet: VehicleFleet, config: dict) -> bool:
        multi_trip_config = config.get("routing", {}).get("multi_trip", {})
        return multi_trip_config.get("enabled", False) and fleet.multiple_trips
