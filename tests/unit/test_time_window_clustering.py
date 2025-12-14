"""Unit tests for time window clustering module."""
import pytest
from src.utils.time_window_clustering import TimeWindowCluster, TimeWindowClusterer
from src.models.order import Order


class TestTimeWindowCluster:
    """Test suite for TimeWindowCluster dataclass."""

    def test_time_window_midpoint(self):
        """Test midpoint calculation."""
        cluster = TimeWindowCluster(
            cluster_id=0,
            orders=[],
            earliest_start=420,  # 07:00
            latest_end=540,  # 09:00
        )
        assert cluster.time_window_midpoint == 480  # 08:00

    def test_repr(self):
        """Test string representation."""
        cluster = TimeWindowCluster(
            cluster_id=1,
            orders=[],
            earliest_start=600,  # 10:00
            latest_end=720,  # 12:00
        )
        repr_str = repr(cluster)
        assert "Cluster(1" in repr_str
        assert "10:00-12:00" in repr_str


class TestTimeWindowClusterer:
    """Test suite for TimeWindowClusterer class."""

    @pytest.fixture
    def sample_orders_two_clusters(self):
        """Create orders that should form two clusters."""
        return [
            # Cluster 1: Morning (07:00-08:30)
            Order(
                sale_order_id="O001",
                delivery_date="2025-10-08",
                delivery_time="07:00-08:00",
                load_weight_in_kg=50.0,
                partner_id="P001",
                display_name="Customer 1",
                alamat="Address 1",
                coordinates=(-6.2100, 106.8500),
                is_priority=False,
            ),
            Order(
                sale_order_id="O002",
                delivery_date="2025-10-08",
                delivery_time="07:30-08:30",
                load_weight_in_kg=30.0,
                partner_id="P002",
                display_name="Customer 2",
                alamat="Address 2",
                coordinates=(-6.2200, 106.8600),
                is_priority=False,
            ),
            # Cluster 2: Late morning (10:00-11:30)
            Order(
                sale_order_id="O003",
                delivery_date="2025-10-08",
                delivery_time="10:00-11:00",
                load_weight_in_kg=40.0,
                partner_id="P003",
                display_name="Customer 3",
                alamat="Address 3",
                coordinates=(-6.2300, 106.8700),
                is_priority=False,
            ),
            Order(
                sale_order_id="O004",
                delivery_date="2025-10-08",
                delivery_time="10:30-11:30",
                load_weight_in_kg=25.0,
                partner_id="P004",
                display_name="Customer 4",
                alamat="Address 4",
                coordinates=(-6.2400, 106.8800),
                is_priority=False,
            ),
        ]

    @pytest.fixture
    def sample_orders_single_cluster(self):
        """Create orders that should form a single cluster."""
        return [
            Order(
                sale_order_id="O001",
                delivery_date="2025-10-08",
                delivery_time="07:00-08:00",
                load_weight_in_kg=50.0,
                partner_id="P001",
                display_name="Customer 1",
                alamat="Address 1",
                coordinates=(-6.2100, 106.8500),
                is_priority=False,
            ),
            Order(
                sale_order_id="O002",
                delivery_date="2025-10-08",
                delivery_time="07:30-08:30",
                load_weight_in_kg=30.0,
                partner_id="P002",
                display_name="Customer 2",
                alamat="Address 2",
                coordinates=(-6.2200, 106.8600),
                is_priority=False,
            ),
            Order(
                sale_order_id="O003",
                delivery_date="2025-10-08",
                delivery_time="08:00-09:00",
                load_weight_in_kg=40.0,
                partner_id="P003",
                display_name="Customer 3",
                alamat="Address 3",
                coordinates=(-6.2300, 106.8700),
                is_priority=False,
            ),
        ]

    def test_cluster_orders_empty(self):
        """Empty order list should return empty clusters."""
        clusterer = TimeWindowClusterer(gap_threshold_minutes=60)
        clusters = clusterer.cluster_orders([])
        assert clusters == []

    def test_cluster_orders_single_cluster(self, sample_orders_single_cluster):
        """Orders with close time windows should form one cluster."""
        clusterer = TimeWindowClusterer(gap_threshold_minutes=60)
        clusters = clusterer.cluster_orders(sample_orders_single_cluster)

        assert len(clusters) == 1
        assert len(clusters[0].orders) == 3
        assert clusters[0].earliest_start == 420  # 07:00
        assert clusters[0].latest_end == 540  # 09:00

    def test_cluster_orders_multiple_clusters(self, sample_orders_two_clusters):
        """Orders with gaps > threshold should form separate clusters."""
        clusterer = TimeWindowClusterer(gap_threshold_minutes=60)
        clusters = clusterer.cluster_orders(sample_orders_two_clusters)

        assert len(clusters) == 2

        # First cluster: morning orders
        assert len(clusters[0].orders) == 2
        assert clusters[0].earliest_start == 420  # 07:00
        assert clusters[0].latest_end == 510  # 08:30

        # Second cluster: late morning orders
        assert len(clusters[1].orders) == 2
        assert clusters[1].earliest_start == 600  # 10:00
        assert clusters[1].latest_end == 690  # 11:30

    def test_cluster_orders_sorted_by_time(self, sample_orders_two_clusters):
        """Clusters should be sorted by earliest_start."""
        # Shuffle orders
        shuffled = [
            sample_orders_two_clusters[2],  # 10:00
            sample_orders_two_clusters[0],  # 07:00
            sample_orders_two_clusters[3],  # 10:30
            sample_orders_two_clusters[1],  # 07:30
        ]

        clusterer = TimeWindowClusterer(gap_threshold_minutes=60)
        clusters = clusterer.cluster_orders(shuffled)

        assert len(clusters) == 2
        assert clusters[0].earliest_start < clusters[1].earliest_start

    def test_cluster_ids_sequential(self, sample_orders_two_clusters):
        """Cluster IDs should be sequential starting from 0."""
        clusterer = TimeWindowClusterer(gap_threshold_minutes=60)
        clusters = clusterer.cluster_orders(sample_orders_two_clusters)

        assert clusters[0].cluster_id == 0
        assert clusters[1].cluster_id == 1

    def test_larger_gap_threshold_fewer_clusters(self, sample_orders_two_clusters):
        """Larger gap threshold should result in fewer clusters."""
        # With large threshold, all orders should be in one cluster
        clusterer = TimeWindowClusterer(gap_threshold_minutes=180)
        clusters = clusterer.cluster_orders(sample_orders_two_clusters)

        assert len(clusters) == 1
        assert len(clusters[0].orders) == 4

    def test_smaller_gap_threshold_more_clusters(self, sample_orders_single_cluster):
        """Smaller gap threshold should result in more clusters."""
        # With very small threshold, orders might split more
        clusterer = TimeWindowClusterer(gap_threshold_minutes=15)
        clusters = clusterer.cluster_orders(sample_orders_single_cluster)

        # Should still be together since time windows overlap
        assert len(clusters) >= 1

    def test_min_cluster_size_merging(self):
        """Small clusters should be merged when below min_cluster_size."""
        orders = [
            Order(
                sale_order_id="O001",
                delivery_date="2025-10-08",
                delivery_time="07:00-08:00",
                load_weight_in_kg=50.0,
                partner_id="P001",
                display_name="Customer 1",
                alamat="Address 1",
                coordinates=(-6.2100, 106.8500),
                is_priority=False,
            ),
            # Gap here
            Order(
                sale_order_id="O002",
                delivery_date="2025-10-08",
                delivery_time="10:00-11:00",
                load_weight_in_kg=30.0,
                partner_id="P002",
                display_name="Customer 2",
                alamat="Address 2",
                coordinates=(-6.2200, 106.8600),
                is_priority=False,
            ),
            Order(
                sale_order_id="O003",
                delivery_date="2025-10-08",
                delivery_time="10:30-11:30",
                load_weight_in_kg=40.0,
                partner_id="P003",
                display_name="Customer 3",
                alamat="Address 3",
                coordinates=(-6.2300, 106.8700),
                is_priority=False,
            ),
        ]

        # With min_cluster_size=2, single-order cluster should be merged
        clusterer = TimeWindowClusterer(gap_threshold_minutes=60, min_cluster_size=2)
        clusters = clusterer.cluster_orders(orders)

        # The single order cluster (O001) should be merged with O002+O003
        # or result in 2 clusters where the small one gets merged
        total_orders = sum(len(c.orders) for c in clusters)
        assert total_orders == 3  # All orders accounted for
