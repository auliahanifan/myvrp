from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np

from ..models.hub_config import HubIndexManager, MultiHubConfig
from ..models.location import Depot
from ..models.order import Order
from ..models.vehicle import VehicleFleet
from ..utils.hub_routing import MultiHubRoutingManager


@dataclass
class SolverContext:
    orders: List[Order]
    fleet: VehicleFleet
    depot: Depot
    multi_hub_config: MultiHubConfig
    hub_routing_manager: MultiHubRoutingManager
    full_distance_matrix: np.ndarray
    full_duration_matrix: np.ndarray
    config: Dict[str, Any]
    index_manager: HubIndexManager
    hub_index_map: Dict[str, int]
    order_index_map: Dict[str, int]
    order_position_map: Dict[str, int]
    _order_identity_map: Dict[int, int]

    @classmethod
    def build(
        cls,
        orders: List[Order],
        fleet: VehicleFleet,
        depot: Depot,
        multi_hub_config: MultiHubConfig,
        hub_routing_manager: MultiHubRoutingManager,
        full_distance_matrix: np.ndarray,
        full_duration_matrix: np.ndarray,
        config: Dict[str, Any] | None = None,
    ) -> "SolverContext":
        hub_ids = multi_hub_config.get_all_hub_ids()
        index_manager = HubIndexManager(hub_ids)
        hub_index_map = {
            hub_id: index_manager.get_hub_index(hub_id)
            for hub_id in hub_ids
        }
        order_index_map = {
            order.sale_order_id: index_manager.get_customer_index(i)
            for i, order in enumerate(orders)
        }
        order_position_map = {
            order.sale_order_id: i
            for i, order in enumerate(orders)
        }
        order_identity_map = {
            id(order): i
            for i, order in enumerate(orders)
        }

        return cls(
            orders=orders,
            fleet=fleet,
            depot=depot,
            multi_hub_config=multi_hub_config,
            hub_routing_manager=hub_routing_manager,
            full_distance_matrix=full_distance_matrix,
            full_duration_matrix=full_duration_matrix,
            config=config or {},
            index_manager=index_manager,
            hub_index_map=hub_index_map,
            order_index_map=order_index_map,
            order_position_map=order_position_map,
            _order_identity_map=order_identity_map,
        )

    def resolve_order_position(self, order: Order) -> int | None:
        if id(order) in self._order_identity_map:
            return self._order_identity_map[id(order)]
        return self.order_position_map.get(order.sale_order_id)
