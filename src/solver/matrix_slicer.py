from typing import List

import numpy as np

from ..models.order import Order
from .solver_context import SolverContext


class MatrixSlicer:
    def __init__(self, context: SolverContext):
        self.context = context

    def get_depot_indices(self, orders: List[Order]) -> List[int]:
        return [self.context.index_manager.get_depot_index(), *self._get_order_indices(orders)]

    def get_hub_indices(self, hub_id: str, orders: List[Order]) -> List[int]:
        return [self.context.index_manager.get_hub_index(hub_id), *self._get_order_indices(orders)]

    def _get_order_indices(self, orders: List[Order]) -> List[int]:
        indices: List[int] = []
        for order in orders:
            order_position = self.context.resolve_order_position(order)
            if order_position is None:
                continue
            indices.append(self.context.index_manager.get_customer_index(order_position))
        return indices

    def extract(self, matrix: np.ndarray, indices: List[int]) -> np.ndarray:
        return self.extract_submatrix(matrix, indices)

    @staticmethod
    def extract_submatrix(matrix: np.ndarray, indices: List[int]) -> np.ndarray:
        return matrix[np.ix_(indices, indices)]
