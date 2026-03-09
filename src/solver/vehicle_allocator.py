from typing import Dict, List

from ..models.order import Order
from ..models.vehicle import VehicleFleet
from .solver_context import SolverContext


class VehicleAllocator:
    UNLIMITED_PLACEHOLDER_COUNT = 50

    def allocate(
        self,
        context: SolverContext,
        orders_by_source: Dict[str, List[Order]],
    ) -> Dict[str, VehicleFleet]:
        source_weights = {
            source_id: sum(order.load_weight_in_kg for order in orders)
            for source_id, orders in orders_by_source.items()
        }
        total_weight = sum(source_weights.values())
        if total_weight == 0:
            return {}

        motor_vehicles = [
            (vehicle, count, unlimited)
            for vehicle, count, unlimited in context.fleet.vehicle_types
            if vehicle.name != context.multi_hub_config.blind_van_vehicle_name
        ]

        allocations: Dict[str, VehicleFleet] = {}
        for source_id, weight in source_weights.items():
            if not orders_by_source.get(source_id):
                continue

            ratio = weight / total_weight if total_weight > 0 else 0
            source_allocation = []
            for vehicle, count, unlimited in motor_vehicles:
                if unlimited:
                    source_allocation.append((vehicle, self.UNLIMITED_PLACEHOLDER_COUNT, True))
                    continue

                allocated_count = max(1, round(count * ratio)) if weight > 0 else 0
                if allocated_count > 0:
                    source_allocation.append((vehicle, allocated_count, False))

            if source_allocation:
                allocations[source_id] = VehicleFleet(
                    vehicle_types=source_allocation,
                    return_to_depot=context.fleet.return_to_depot,
                    priority_time_tolerance=context.fleet.priority_time_tolerance,
                    non_priority_time_tolerance=context.fleet.non_priority_time_tolerance,
                    multiple_trips=context.fleet.multiple_trips,
                    relax_time_windows=context.fleet.relax_time_windows,
                    time_window_relaxation_minutes=context.fleet.time_window_relaxation_minutes,
                )

        return allocations
