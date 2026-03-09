"""
Multi-hub facade that orchestrates classification and routing stages.
"""
from typing import Dict, List
import time as time_module

from ..models.hub_config import MultiHubConfig
from ..models.location import Depot
from ..models.order import Order
from ..models.route import RoutingSolution
from ..models.vehicle import VehicleFleet
from ..utils.hub_routing import MultiHubRoutingManager
from .order_classifier import ClassificationResult, OrderClassifier
from .solver_context import SolverContext
from .tier1_blind_van_service import Tier1BlindVanService
from .tier2_source_router import Tier2SourceRouter
from .vehicle_allocator import VehicleAllocator


class TwoTierRoutingError(Exception):
    """Custom exception for two-tier routing errors."""


class MultiHubVRPSolver:
    def __init__(
        self,
        orders: List[Order],
        fleet: VehicleFleet,
        depot: Depot,
        multi_hub_config: MultiHubConfig,
        hub_routing_manager: MultiHubRoutingManager,
        full_distance_matrix,
        full_duration_matrix,
        config: dict = None,
    ):
        self.context = SolverContext.build(
            orders=orders,
            fleet=fleet,
            depot=depot,
            multi_hub_config=multi_hub_config,
            hub_routing_manager=hub_routing_manager,
            full_distance_matrix=full_distance_matrix,
            full_duration_matrix=full_duration_matrix,
            config=config or {},
        )
        self.orders = self.context.orders
        self.fleet = self.context.fleet
        self.depot = self.context.depot
        self.hub_config = self.context.multi_hub_config
        self.hub_manager = self.context.hub_routing_manager
        self.full_distance_matrix = self.context.full_distance_matrix
        self.full_duration_matrix = self.context.full_duration_matrix
        self.config = self.context.config

    def solve(
        self,
        optimization_strategy: str = "balanced",
        time_limit: int = 300,
    ) -> RoutingSolution:
        start_time = time_module.time()

        try:
            classification = OrderClassifier().classify(self.context)
            self._print_lines(classification.summary_lines)

            if self.hub_config.is_zero_hub_mode:
                print("\n[Zero Hub Mode] All orders routing directly from DEPOT")
                solution = Tier2SourceRouter().solve_zero_hub(
                    context=self.context,
                    optimization_strategy=optimization_strategy,
                    time_limit=time_limit,
                )
                solution.optimization_strategy = optimization_strategy
                solution.computation_time = time_module.time() - start_time
                return solution

            tier1_result = Tier1BlindVanService().solve(
                context=self.context,
                classification=classification,
                time_limit=time_limit,
            )
            self._print_lines(tier1_result.log_lines)

            effective_classification = self._remove_delivered_orders(
                classification,
                tier1_result.delivered_en_route_order_ids,
            )
            allocated_fleets = VehicleAllocator().allocate(
                self.context,
                effective_classification.orders_by_source,
            )
            tier2_result = Tier2SourceRouter().solve_all_sources(
                context=self.context,
                classification=effective_classification,
                allocated_fleets=allocated_fleets,
                optimization_strategy=optimization_strategy,
                time_limit=time_limit,
                vehicle_offset=len(tier1_result.routes),
            )
            self._print_lines(tier2_result.log_lines)

            computation_time = time_module.time() - start_time
            return RoutingSolution(
                routes=[*tier1_result.routes, *tier2_result.routes],
                unassigned_orders=tier2_result.unassigned_orders,
                optimization_strategy=optimization_strategy,
                computation_time=computation_time,
            )
        except Exception as exc:
            raise TwoTierRoutingError(f"Multi-hub routing failed: {exc}")

    def get_routing_summary(self) -> Dict:
        return self.hub_manager.get_routing_summary(self.orders)

    def _remove_delivered_orders(
        self,
        classification: ClassificationResult,
        delivered_order_ids: set[str],
    ) -> ClassificationResult:
        if not delivered_order_ids:
            return classification

        filtered_orders = {
            source_id: [
                order
                for order in orders
                if order.sale_order_id not in delivered_order_ids
            ]
            for source_id, orders in classification.orders_by_source.items()
        }
        return ClassificationResult(
            orders_by_source=filtered_orders,
            summary_lines=classification.summary_lines,
            delivered_en_route_order_ids=delivered_order_ids,
        )

    def _print_lines(self, lines: List[str]) -> None:
        for line in lines:
            print(line)


TwoTierVRPSolver = MultiHubVRPSolver
