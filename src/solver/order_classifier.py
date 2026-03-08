from dataclasses import dataclass, field
from typing import Dict, List

from ..models.order import Order
from ..utils.hub_routing import MultiHubRoutingManager
from .dynamic_source_assigner import DynamicSourceAssigner
from .solver_context import SolverContext


@dataclass
class ClassificationResult:
    orders_by_source: Dict[str, List[Order]]
    summary_lines: List[str]
    delivered_en_route_order_ids: set[str] = field(default_factory=set)


class OrderClassifier:
    def classify(self, context: SolverContext) -> ClassificationResult:
        source_assignment = context.multi_hub_config.source_assignment
        zone_assignments = context.hub_routing_manager.classify_orders_zone_based(context.orders)

        if source_assignment.mode == "zone_based":
            orders_by_source = zone_assignments
        else:
            assigner = DynamicSourceAssigner(
                depot=context.depot,
                hub_configs=context.multi_hub_config.hubs,
                distance_matrix=context.full_distance_matrix,
                duration_matrix=context.full_duration_matrix,
                config=source_assignment,
                hub_index_map=context.hub_index_map,
                order_index_offset=context.index_manager.customer_start_index,
            )
            orders_by_source = assigner.assign_orders(context.orders, zone_assignments)
            if not orders_by_source or all(len(orders) == 0 for orders in orders_by_source.values()):
                orders_by_source = zone_assignments
                assignment_summary = None
            else:
                assignment_summary = assigner.get_assignment_summary(context.orders, orders_by_source)
        summary_lines = self._build_summary_lines(context, orders_by_source)

        if source_assignment.mode != "zone_based" and assignment_summary is not None:
            summary_lines.insert(0, f"[Source Assignment] Mode: {assignment_summary['assignment_mode']}")
            summary_lines.insert(
                1,
                f"  Threshold: {assignment_summary['cost_threshold_percent']}% cost advantage required to switch",
            )

        return ClassificationResult(
            orders_by_source=orders_by_source,
            summary_lines=summary_lines,
        )

    def _build_summary_lines(
        self,
        context: SolverContext,
        orders_by_source: Dict[str, List[Order]],
    ) -> List[str]:
        lines = ["[Multi-Hub VRP] Order Classification:"]
        total_hub_orders = 0
        total_hub_weight = 0.0

        for source_id, source_orders in orders_by_source.items():
            weight = sum(order.load_weight_in_kg for order in source_orders)
            if source_id == MultiHubRoutingManager.DIRECT_KEY:
                lines.append(f"  DEPOT (direct): {len(source_orders)} orders, {weight:.1f} kg")
                continue

            hub_config = context.multi_hub_config.get_hub_by_id(source_id)
            hub_name = hub_config.hub.name if hub_config else source_id
            mode = hub_config.blind_van_config.mode.value if hub_config else "unknown"
            lines.append(
                f"  {hub_name} ({source_id}): {len(source_orders)} orders, {weight:.1f} kg [Mode: {mode}]"
            )
            total_hub_orders += len(source_orders)
            total_hub_weight += weight

        lines.append(f"  Total hub orders: {total_hub_orders}, Total hub weight: {total_hub_weight:.1f} kg")
        lines.append(f"  Blind van return to depot: {context.multi_hub_config.blind_van_return_to_depot}")
        return lines
