"""
Unit tests for smart routing components.

Tests:
- BlindVanMode configuration
- Dynamic source assignment
- Blind van router with Mode A/B
"""
import pytest
import numpy as np
from src.models.order import Order
from src.models.location import Depot, Hub
from src.models.vehicle import Vehicle, VehicleFleet
from src.models.hub_config import (
    BlindVanMode,
    EnRouteDeliveryConfig,
    HubBlindVanConfig,
    SourceAssignmentConfig,
    HubConfig,
    MultiHubConfig,
)
from src.solver.dynamic_source_assigner import DynamicSourceAssigner
from src.solver.blind_van_router import BlindVanRouter


class TestBlindVanModeConfig:
    """Test BlindVanMode configuration."""

    def test_mode_a_consolidation_only(self):
        """Mode A should have delivery disabled by default."""
        config = HubBlindVanConfig(mode=BlindVanMode.CONSOLIDATION_ONLY)
        assert config.mode == BlindVanMode.CONSOLIDATION_ONLY
        assert not config.is_delivery_enabled

    def test_mode_b_with_delivery_config(self):
        """Mode B with en_route config should enable delivery if max_stops > 0."""
        en_route = EnRouteDeliveryConfig(
            max_stops=3,
            max_detour_minutes=10,
            max_detour_km=5.0,
        )
        config = HubBlindVanConfig(
            mode=BlindVanMode.CONSOLIDATION_WITH_DELIVERY,
            en_route_delivery=en_route,
        )
        assert config.mode == BlindVanMode.CONSOLIDATION_WITH_DELIVERY
        assert config.is_delivery_enabled

    def test_mode_b_zero_stops_disabled(self):
        """Mode B with max_stops=0 should have delivery disabled."""
        en_route = EnRouteDeliveryConfig(max_stops=0)
        config = HubBlindVanConfig(
            mode=BlindVanMode.CONSOLIDATION_WITH_DELIVERY,
            en_route_delivery=en_route,
        )
        assert not config.is_delivery_enabled

    def test_mode_b_auto_creates_en_route_config(self):
        """Mode B without en_route config should auto-create default."""
        config = HubBlindVanConfig(mode=BlindVanMode.CONSOLIDATION_WITH_DELIVERY)
        assert config.en_route_delivery is not None


class TestSourceAssignmentConfig:
    """Test source assignment configuration."""

    def test_default_zone_based(self):
        """Default should be zone_based mode."""
        config = SourceAssignmentConfig()
        assert config.mode == "zone_based"
        assert config.min_cost_advantage_percent == 10.0

    def test_hybrid_mode(self):
        """Hybrid mode with custom weights."""
        config = SourceAssignmentConfig(
            mode="hybrid",
            min_cost_advantage_percent=15.0,
            distance_weight=1.5,
            time_weight=0.3,
        )
        assert config.mode == "hybrid"
        assert config.min_cost_advantage_percent == 15.0
        assert config.distance_weight == 1.5
        assert config.time_weight == 0.3


class TestMultiHubConfigExtended:
    """Test extended MultiHubConfig with new fields."""

    @pytest.fixture
    def hub_with_mode_a(self):
        hub = Hub(name="Hub A", coordinates=(-6.2, 106.8))
        return HubConfig(
            hub=hub,
            hub_id="hub_a",
            zones_via_hub=["JAKARTA UTARA"],
            blind_van_config=HubBlindVanConfig(mode=BlindVanMode.CONSOLIDATION_ONLY),
        )

    @pytest.fixture
    def hub_with_mode_b(self):
        hub = Hub(name="Hub B", coordinates=(-6.3, 106.9))
        en_route = EnRouteDeliveryConfig(max_stops=3)
        return HubConfig(
            hub=hub,
            hub_id="hub_b",
            zones_via_hub=["JAKARTA SELATAN"],
            blind_van_config=HubBlindVanConfig(
                mode=BlindVanMode.CONSOLIDATION_WITH_DELIVERY,
                en_route_delivery=en_route,
            ),
        )

    def test_get_hubs_with_delivery(self, hub_with_mode_a, hub_with_mode_b):
        """Should return only hubs with Mode B delivery enabled."""
        config = MultiHubConfig(
            hubs=[hub_with_mode_a, hub_with_mode_b],
            enabled=True,
        )
        delivery_hubs = config.get_hubs_with_delivery()
        assert len(delivery_hubs) == 1
        assert delivery_hubs[0].hub_id == "hub_b"

    def test_get_hubs_consolidation_only(self, hub_with_mode_a, hub_with_mode_b):
        """Should return only hubs with Mode A."""
        config = MultiHubConfig(
            hubs=[hub_with_mode_a, hub_with_mode_b],
            enabled=True,
        )
        consolidation_hubs = config.get_hubs_consolidation_only()
        assert len(consolidation_hubs) == 1
        assert consolidation_hubs[0].hub_id == "hub_a"

    def test_has_any_delivery_enabled(self, hub_with_mode_a, hub_with_mode_b):
        """Should detect if any hub has delivery enabled."""
        config_with_delivery = MultiHubConfig(
            hubs=[hub_with_mode_a, hub_with_mode_b],
            enabled=True,
        )
        assert config_with_delivery.has_any_delivery_enabled()

        config_no_delivery = MultiHubConfig(
            hubs=[hub_with_mode_a],
            enabled=True,
        )
        assert not config_no_delivery.has_any_delivery_enabled()

    def test_return_to_depot_default(self):
        """Default should be False (can end at hub)."""
        config = MultiHubConfig()
        assert not config.blind_van_return_to_depot


class TestDynamicSourceAssigner:
    """Test dynamic source assignment logic."""

    @pytest.fixture
    def sample_depot(self):
        return Depot(
            name="Warehouse",
            coordinates=(-6.2088, 106.8456),
        )

    @pytest.fixture
    def sample_hub_configs(self):
        hub = Hub(name="Hub Utara", coordinates=(-6.1646, 106.8716))
        return [
            HubConfig(
                hub=hub,
                hub_id="hub_utara",
                zones_via_hub=["JAKARTA UTARA"],
            )
        ]

    @pytest.fixture
    def sample_orders(self):
        return [
            Order(
                sale_order_id="O001",
                delivery_date="2025-01-01",
                delivery_time="08:00-10:00",
                load_weight_in_kg=10,
                partner_id="P1",
                display_name="Customer 1",
                alamat="Jakarta Utara",
                coordinates=(-6.15, 106.87),  # Close to hub
                kota="JAKARTA UTARA",
            ),
            Order(
                sale_order_id="O002",
                delivery_date="2025-01-01",
                delivery_time="09:00-11:00",
                load_weight_in_kg=15,
                partner_id="P2",
                display_name="Customer 2",
                alamat="Jakarta Selatan",
                coordinates=(-6.25, 106.85),  # Close to depot
                kota="JAKARTA SELATAN",
            ),
        ]

    @pytest.fixture
    def sample_matrices(self):
        # Simple 4x4 matrix: [DEPOT, HUB, Order1, Order2]
        distance = np.array([
            [0, 10, 15, 5],    # From DEPOT
            [10, 0, 5, 20],    # From HUB
            [15, 5, 0, 25],    # From Order1
            [5, 20, 25, 0],    # From Order2
        ])
        duration = distance * 2  # 2 minutes per km
        return distance, duration

    def test_assigner_initialization(self, sample_depot, sample_hub_configs, sample_matrices):
        """Test DynamicSourceAssigner initialization."""
        distance, duration = sample_matrices
        config = SourceAssignmentConfig(mode="hybrid")

        assigner = DynamicSourceAssigner(
            depot=sample_depot,
            hub_configs=sample_hub_configs,
            distance_matrix=distance,
            duration_matrix=duration,
            config=config,
            hub_index_map={"hub_utara": 1},
            order_index_offset=2,
        )

        assert assigner.depot == sample_depot
        assert len(assigner.hub_configs) == 1

    def test_compute_source_cost(self, sample_depot, sample_hub_configs, sample_matrices):
        """Test cost computation from different sources."""
        distance, duration = sample_matrices
        config = SourceAssignmentConfig(
            mode="hybrid",
            distance_weight=1.0,
            time_weight=0.5,
        )

        assigner = DynamicSourceAssigner(
            depot=sample_depot,
            hub_configs=sample_hub_configs,
            distance_matrix=distance,
            duration_matrix=duration,
            config=config,
            hub_index_map={"hub_utara": 1},
            order_index_offset=2,
        )

        # Create a sample order
        order = Order(
            sale_order_id="O001",
            delivery_date="2025-01-01",
            delivery_time="08:00",
            load_weight_in_kg=10,
            partner_id="P1",
            display_name="Test",
            alamat="Test",
            coordinates=(-6.15, 106.87),
        )

        # Cost from DEPOT (index 0 -> 2): distance=15, duration=30
        # Expected: 1.0*15 + 0.5*30 = 30
        depot_cost = assigner.compute_source_cost(order, 0, "DEPOT")
        assert depot_cost.source_id == "DEPOT"
        assert depot_cost.distance_km == 15
        assert depot_cost.duration_minutes == 30
        assert depot_cost.total_cost == 30

        # Cost from HUB (index 1 -> 2): distance=5, duration=10
        # Expected: 1.0*5 + 0.5*10 = 10
        hub_cost = assigner.compute_source_cost(order, 0, "hub_utara")
        assert hub_cost.source_id == "hub_utara"
        assert hub_cost.distance_km == 5
        assert hub_cost.duration_minutes == 10
        assert hub_cost.total_cost == 10

    def test_find_best_source(self, sample_depot, sample_hub_configs, sample_matrices):
        """Test finding best source for an order."""
        distance, duration = sample_matrices
        config = SourceAssignmentConfig(mode="dynamic")

        assigner = DynamicSourceAssigner(
            depot=sample_depot,
            hub_configs=sample_hub_configs,
            distance_matrix=distance,
            duration_matrix=duration,
            config=config,
            hub_index_map={"hub_utara": 1},
            order_index_offset=2,
        )

        order = Order(
            sale_order_id="O001",
            delivery_date="2025-01-01",
            delivery_time="08:00",
            load_weight_in_kg=10,
            partner_id="P1",
            display_name="Test",
            alamat="Test",
            coordinates=(-6.15, 106.87),
        )

        # Order at index 0 is closer to HUB (cost 10) than DEPOT (cost 30)
        best_source, best_cost = assigner.find_best_source(order, 0)
        assert best_source == "hub_utara"

    def test_zone_based_assignment(self, sample_depot, sample_hub_configs, sample_matrices, sample_orders):
        """Test zone-based assignment fallback."""
        distance, duration = sample_matrices
        config = SourceAssignmentConfig(mode="zone_based")

        assigner = DynamicSourceAssigner(
            depot=sample_depot,
            hub_configs=sample_hub_configs,
            distance_matrix=distance,
            duration_matrix=duration,
            config=config,
            hub_index_map={"hub_utara": 1},
            order_index_offset=2,
        )

        # Order 1 is in JAKARTA UTARA (hub zone)
        source1 = assigner.get_zone_based_source(sample_orders[0])
        assert source1 == "hub_utara"

        # Order 2 is in JAKARTA SELATAN (not in hub zone)
        source2 = assigner.get_zone_based_source(sample_orders[1])
        assert source2 == "DEPOT"


class TestYAMLParserSmartRouting:
    """Test YAML parser with new smart routing config."""

    def test_parse_conf_yaml(self):
        """Test parsing the actual conf.yaml file."""
        from src.utils.yaml_parser import YAMLParser

        parser = YAMLParser("conf.yaml")
        fleet = parser.parse()
        hub_config = parser.get_hubs_config()

        # Should parse successfully
        assert hub_config.enabled
        assert hub_config.source_assignment.mode == "hybrid"
        assert not hub_config.blind_van_return_to_depot

        # First hub should have blind van config
        if hub_config.hubs:
            first_hub = hub_config.hubs[0]
            assert first_hub.blind_van_config is not None
            assert first_hub.blind_van_config.mode == BlindVanMode.CONSOLIDATION_ONLY
