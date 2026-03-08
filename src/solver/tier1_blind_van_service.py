from dataclasses import dataclass, field
from typing import List

from ..models.route import Route
from ..utils.hub_routing import MultiHubRoutingManager
from .blind_van_router import BlindVanRouter
from .order_classifier import ClassificationResult
from .solver_context import SolverContext


@dataclass
class Tier1Result:
    routes: List[Route]
    delivered_en_route_order_ids: set[str]
    log_lines: List[str] = field(default_factory=list)


class Tier1BlindVanService:
    def solve(
        self,
        context: SolverContext,
        classification: ClassificationResult,
        time_limit: int,
    ) -> Tier1Result:
        del time_limit

        hubs_with_orders = [
            hub_id
            for hub_id, orders in classification.orders_by_source.items()
            if hub_id != MultiHubRoutingManager.DIRECT_KEY and orders
        ]
        if not hubs_with_orders:
            return Tier1Result(
                routes=[],
                delivered_en_route_order_ids=set(),
                log_lines=["[Tier 1] No hub orders, skipping Blind Van"],
            )

        blind_van = self._get_blind_van_vehicle(context)
        if blind_van is None:
            return Tier1Result(
                routes=[],
                delivered_en_route_order_ids=set(),
                log_lines=["[Tier 1] Warning: Blind Van not found in fleet, skipping consolidation"],
            )

        active_hub_configs = [
            context.multi_hub_config.get_hub_by_id(hub_id)
            for hub_id in hubs_with_orders
            if context.multi_hub_config.get_hub_by_id(hub_id) is not None
        ]
        router = BlindVanRouter(
            depot=context.depot,
            hub_configs=active_hub_configs,
            orders=context.orders,
            classified_orders=classification.orders_by_source,
            blind_van=blind_van,
            distance_matrix=context.full_distance_matrix,
            duration_matrix=context.full_duration_matrix,
            multi_hub_config=context.multi_hub_config,
            hub_index_map=context.hub_index_map,
            order_index_map=context.order_index_map,
        )
        route = router.solve()
        if route is None:
            return Tier1Result(
                routes=[],
                delivered_en_route_order_ids=set(),
                log_lines=["[Tier 1] BlindVanRouter returned no route"],
            )

        delivered_ids = {order.sale_order_id for order in router.get_delivered_orders()}
        summary = router.get_route_summary(route)
        return Tier1Result(
            routes=[route],
            delivered_en_route_order_ids=delivered_ids,
            log_lines=[
                "[Tier 1] Solving Blind Van multi-hub consolidation...",
                f"[Tier 1] En-route deliveries: {len(delivered_ids)} orders",
                f"[Tier 1]   Total stops: {summary['total_stops']} (deliveries: {summary['delivery_stops']}, hubs: {summary['hub_stops']})",
                f"[Tier 1]   Distance: {route.total_distance:.1f} km, Cost: Rp {route.total_cost:,.0f}",
            ],
        )

    def _get_blind_van_vehicle(self, context: SolverContext):
        for vehicle, _, _ in context.fleet.vehicle_types:
            if vehicle.name == context.multi_hub_config.blind_van_vehicle_name:
                return vehicle
        return None
