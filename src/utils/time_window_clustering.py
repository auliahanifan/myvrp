"""
Time Window Clustering for Multi-Trip Routing.

Clusters orders by their time windows to enable multi-trip solving.
Each cluster is solved independently, then vehicles are assigned across trips.
"""
from dataclasses import dataclass
from typing import List

from ..models.order import Order


@dataclass
class TimeWindowCluster:
    """Represents a cluster of orders with similar time windows."""

    cluster_id: int
    orders: List[Order]
    earliest_start: int  # Minutes from midnight
    latest_end: int  # Minutes from midnight

    @property
    def time_window_midpoint(self) -> int:
        """Midpoint of the cluster's time window."""
        return (self.earliest_start + self.latest_end) // 2

    def __repr__(self) -> str:
        start_h, start_m = divmod(self.earliest_start, 60)
        end_h, end_m = divmod(self.latest_end, 60)
        return (
            f"Cluster({self.cluster_id}, {len(self.orders)} orders, "
            f"{start_h:02d}:{start_m:02d}-{end_h:02d}:{end_m:02d})"
        )


class TimeWindowClusterer:
    """Clusters orders by time window proximity."""

    def __init__(
        self,
        gap_threshold_minutes: int = 60,
        min_cluster_size: int = 1,
    ):
        """
        Initialize the clusterer.

        Args:
            gap_threshold_minutes: Minimum gap between time windows to form
                                   separate clusters.
            min_cluster_size: Minimum number of orders per cluster.
        """
        self.gap_threshold = gap_threshold_minutes
        self.min_cluster_size = min_cluster_size

    def cluster_orders(self, orders: List[Order]) -> List[TimeWindowCluster]:
        """
        Cluster orders by time window gaps.

        Algorithm:
        1. Sort orders by time_window_start
        2. Group consecutive orders where gap < threshold
        3. Merge small clusters with nearest neighbor

        Args:
            orders: List of orders to cluster.

        Returns:
            List of TimeWindowCluster sorted by earliest_start.
        """
        if not orders:
            return []

        # Sort by time window start
        sorted_orders = sorted(orders, key=lambda o: o.time_window_start)

        clusters: List[TimeWindowCluster] = []
        current_cluster_orders = [sorted_orders[0]]
        current_end = sorted_orders[0].time_window_end

        for order in sorted_orders[1:]:
            gap = order.time_window_start - current_end

            if gap > self.gap_threshold:
                # Start new cluster
                clusters.append(
                    self._create_cluster(len(clusters), current_cluster_orders)
                )
                current_cluster_orders = [order]
                current_end = order.time_window_end
            else:
                # Add to current cluster
                current_cluster_orders.append(order)
                current_end = max(current_end, order.time_window_end)

        # Add final cluster
        if current_cluster_orders:
            clusters.append(
                self._create_cluster(len(clusters), current_cluster_orders)
            )

        # Merge small clusters
        clusters = self._merge_small_clusters(clusters)

        # Re-number clusters after merging
        for i, cluster in enumerate(clusters):
            cluster.cluster_id = i

        return clusters

    def _create_cluster(
        self, cluster_id: int, orders: List[Order]
    ) -> TimeWindowCluster:
        """Create a TimeWindowCluster from orders."""
        return TimeWindowCluster(
            cluster_id=cluster_id,
            orders=orders,
            earliest_start=min(o.time_window_start for o in orders),
            latest_end=max(o.time_window_end for o in orders),
        )

    def _merge_small_clusters(
        self, clusters: List[TimeWindowCluster]
    ) -> List[TimeWindowCluster]:
        """Merge clusters smaller than min_cluster_size with nearest neighbor."""
        if len(clusters) <= 1:
            return clusters

        result: List[TimeWindowCluster] = []

        for cluster in clusters:
            if len(cluster.orders) < self.min_cluster_size and result:
                # Merge with previous cluster
                prev = result[-1]
                merged_orders = prev.orders + cluster.orders
                result[-1] = self._create_cluster(prev.cluster_id, merged_orders)
            else:
                result.append(cluster)

        # Handle edge case: first cluster is too small
        if result and len(result[0].orders) < self.min_cluster_size and len(result) > 1:
            # Merge first with second
            merged_orders = result[0].orders + result[1].orders
            result[1] = self._create_cluster(0, merged_orders)
            result = result[1:]

        return result
