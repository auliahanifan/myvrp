"""
End-to-end test for smart routing with real order data.

Tests:
- Load real orders from CSV
- Generate distance matrix via OSRM
- Run hybrid source assignment
- Run blind van router
- Solve full two-tier VRP
"""
import pytest
import pandas as pd
from pathlib import Path

from src.models.order import Order
from src.models.location import Depot, Hub
from src.utils.yaml_parser import YAMLParser
from src.utils.distance_calculator import DistanceCalculator
from src.utils.hub_routing import MultiHubRoutingManager
from src.solver.dynamic_source_assigner import DynamicSourceAssigner
from src.solver.blind_van_router import BlindVanRouter
from src.models.hub_config import BlindVanMode


def load_orders_from_csv(csv_path: str) -> list[Order]:
    """Load orders from CSV file."""
    df = pd.read_csv(csv_path)
    orders = []

    for _, row in df.iterrows():
        order = Order(
            sale_order_id=str(row['sale_order_id']),
            delivery_date=str(row['delivery_date']).split('T')[0] if 'T' in str(row['delivery_date']) else str(row['delivery_date']),
            delivery_time=str(row['delivery_time']),
            load_weight_in_kg=float(row['load_weight_in_kg']),
            partner_id=str(row['partner_id']),
            display_name=str(row['display_name']),
            alamat=str(row['alamat']),
            coordinates=(float(row['partner_latitude']), float(row['partner_longitude'])),
            kota=str(row['kota']) if pd.notna(row.get('kota')) else None,
            kecamatan=str(row['kecamatan']) if pd.notna(row.get('kecamatan')) else None,
            is_priority=bool(row.get('is_priority', False)),
        )
        orders.append(order)

    return orders


class TestSmartRoutingEndToEnd:
    """End-to-end tests for smart routing system."""

    @pytest.fixture
    def csv_path(self):
        return Path(__file__).parent.parent.parent / "example" / "example_input.csv"

    @pytest.fixture
    def yaml_parser(self):
        parser = YAMLParser("conf.yaml")
        parser.parse()  # Load data so get_hubs_config() works
        return parser

    @pytest.fixture
    def orders(self, csv_path):
        return load_orders_from_csv(str(csv_path))

    @pytest.fixture
    def depot(self):
        return Depot(
            name="Warehouse Segarloka",
            coordinates=(-6.264818, 106.786922),
        )

    def test_load_orders(self, orders):
        """Test loading orders from CSV."""
        assert len(orders) > 0
        print(f"\n✅ Loaded {len(orders)} orders")

        # Check order distribution by kota
        kota_counts = {}
        for order in orders:
            kota = order.kota or "UNKNOWN"
            kota_counts[kota] = kota_counts.get(kota, 0) + 1

        print("\nOrder distribution by kota:")
        for kota, count in sorted(kota_counts.items(), key=lambda x: -x[1]):
            print(f"  {kota}: {count}")

    def test_yaml_config_parsing(self, yaml_parser):
        """Test YAML config with new smart routing fields."""
        fleet = yaml_parser.parse()
        hub_config = yaml_parser.get_hubs_config()

        assert hub_config is not None
        assert hub_config.enabled

        print(f"\n✅ Hub config parsed:")
        print(f"  - Enabled: {hub_config.enabled}")
        print(f"  - Source assignment mode: {hub_config.source_assignment.mode}")
        print(f"  - Return to depot: {hub_config.blind_van_return_to_depot}")
        print(f"  - Hubs: {len(hub_config.hubs)}")

        for hc in hub_config.hubs:
            print(f"\n  Hub: {hc.hub.name} ({hc.hub_id})")
            print(f"    - Zones: {hc.zones_via_hub}")
            print(f"    - Blind van mode: {hc.blind_van_config.mode.value}")
            if hc.blind_van_config.en_route_delivery:
                en_route = hc.blind_van_config.en_route_delivery
                print(f"    - En-route max_stops: {en_route.max_stops}")

    def test_zone_based_classification(self, yaml_parser, orders, depot):
        """Test zone-based order classification."""
        hub_config = yaml_parser.get_hubs_config()

        manager = MultiHubRoutingManager(hub_config, depot)
        classified = manager.classify_orders(orders)

        print(f"\n✅ Zone-based classification:")
        for source, source_orders in classified.items():
            weight = sum(o.load_weight_in_kg for o in source_orders)
            print(f"  {source}: {len(source_orders)} orders, {weight:.1f} kg")

    @pytest.mark.integration
    def test_distance_matrix_generation(self, yaml_parser, orders, depot):
        """Test distance matrix generation via OSRM."""
        hub_config = yaml_parser.get_hubs_config()

        # Build location list: depot + hubs + orders
        locations = [depot]
        hub_index_map = {}

        for idx, hc in enumerate(hub_config.hubs, start=1):
            locations.append(hc.hub)
            hub_index_map[hc.hub_id] = idx

        order_index_offset = len(locations)

        # Limit orders for faster testing
        test_orders = orders[:20]  # Use first 20 orders
        for order in test_orders:
            locations.append(order)

        print(f"\n📡 Generating distance matrix for {len(locations)} locations...")

        calculator = DistanceCalculator()
        distance_matrix, duration_matrix = calculator.calculate_matrix(locations)

        print(f"✅ Distance matrix shape: {distance_matrix.shape}")
        print(f"✅ Duration matrix shape: {duration_matrix.shape}")

        # Print some sample distances
        print(f"\nSample distances from DEPOT:")
        print(f"  DEPOT -> Hub: {distance_matrix[0][1]:.2f} km, {duration_matrix[0][1]:.1f} min")
        print(f"  DEPOT -> Order1: {distance_matrix[0][order_index_offset]:.2f} km")
        print(f"  Hub -> Order1: {distance_matrix[1][order_index_offset]:.2f} km")

        return distance_matrix, duration_matrix, hub_index_map, order_index_offset

    @pytest.mark.integration
    def test_dynamic_source_assignment(self, yaml_parser, orders, depot):
        """Test dynamic/hybrid source assignment."""
        hub_config = yaml_parser.get_hubs_config()

        # Build locations and matrix
        locations = [depot]
        hub_index_map = {}

        for idx, hc in enumerate(hub_config.hubs, start=1):
            locations.append(hc.hub)
            hub_index_map[hc.hub_id] = idx

        order_index_offset = len(locations)
        test_orders = orders[:30]  # Use first 30 orders

        for order in test_orders:
            locations.append(order)

        calculator = DistanceCalculator()
        distance_matrix, duration_matrix = calculator.calculate_matrix(locations)

        # Run dynamic source assigner
        assigner = DynamicSourceAssigner(
            depot=depot,
            hub_configs=hub_config.hubs,
            distance_matrix=distance_matrix,
            duration_matrix=duration_matrix,
            config=hub_config.source_assignment,
            hub_index_map=hub_index_map,
            order_index_offset=order_index_offset,
        )

        # Compare zone-based vs hybrid
        print(f"\n🔄 Comparing assignment modes:")

        zone_result = {}
        for idx, order in enumerate(test_orders):
            source = assigner.get_zone_based_source(order)
            if source not in zone_result:
                zone_result[source] = []
            zone_result[source].append(order)

        print(f"\nZone-based assignment:")
        for source, source_orders in zone_result.items():
            print(f"  {source}: {len(source_orders)} orders")

        # Hybrid assignment
        hybrid_result = assigner.assign_orders(test_orders)

        print(f"\nHybrid assignment (mode={hub_config.source_assignment.mode}):")
        for source, source_orders in hybrid_result.items():
            if source_orders:
                print(f"  {source}: {len(source_orders)} orders")

        # Show differences
        if hub_config.source_assignment.mode in ["hybrid", "dynamic"]:
            depot_zone = len(zone_result.get("DEPOT", []))
            depot_hybrid = len(hybrid_result.get("DEPOT", []))
            diff = depot_hybrid - depot_zone
            if diff != 0:
                print(f"\n📊 Hybrid assignment moved {abs(diff)} orders {'to' if diff > 0 else 'from'} DEPOT")

    @pytest.mark.integration
    def test_full_solver_run(self, yaml_parser, orders, depot):
        """Test full two-tier VRP solver with smart routing."""
        from src.solver.two_tier_vrp_solver import MultiHubVRPSolver

        # Use subset of orders for faster testing
        test_orders = orders[:50]

        print(f"\n🚀 Running full solver with {len(test_orders)} orders...")

        fleet = yaml_parser.parse()
        hub_config = yaml_parser.get_hubs_config()
        config = yaml_parser.get_config()

        # Create hub routing manager
        hub_routing_manager = MultiHubRoutingManager(hub_config, depot)

        # Build location list for matrix: depot + hubs + orders
        locations = [depot]
        for hc in hub_config.hubs:
            locations.append(hc.hub)
        for order in test_orders:
            locations.append(order)

        print(f"📡 Generating distance matrix for {len(locations)} locations...")
        calculator = DistanceCalculator()
        distance_matrix, duration_matrix = calculator.calculate_matrix(locations)
        print(f"✅ Matrix generated: {distance_matrix.shape}")

        solver = MultiHubVRPSolver(
            orders=test_orders,
            fleet=fleet,
            depot=depot,
            multi_hub_config=hub_config,
            hub_routing_manager=hub_routing_manager,
            full_distance_matrix=distance_matrix,
            full_duration_matrix=duration_matrix,
            config=config,
        )

        solution = solver.solve()

        print(f"\n✅ Solution generated:")
        print(f"  - Total routes: {len(solution.routes)}")
        print(f"  - Total distance: {solution.total_distance:.1f} km")
        print(f"  - Total cost: Rp {solution.total_cost:,.0f}")
        print(f"  - Orders delivered: {solution.total_orders_delivered}")
        print(f"  - Unassigned orders: {len(solution.unassigned_orders)}")

        # Analyze routes by source
        depot_routes = [r for r in solution.routes if r.source == "DEPOT"]
        hub_routes = [r for r in solution.routes if r.source != "DEPOT"]

        print(f"\nRoutes breakdown:")
        print(f"  - From DEPOT: {len(depot_routes)} routes")
        print(f"  - From HUBs: {len(hub_routes)} routes")

        # Check for blind van route
        blind_van_routes = [r for r in solution.routes if "Blind Van" in r.vehicle.name]
        if blind_van_routes:
            bv = blind_van_routes[0]
            print(f"\nBlind Van Route:")
            print(f"  - Stops: {len(bv.stops)}")
            print(f"  - Distance: {bv.total_distance:.1f} km")

            # Check for en-route deliveries
            en_route = [s for s in bv.stops if not s.order.sale_order_id.startswith("HUB_CONSOLIDATION")]
            hub_stops = [s for s in bv.stops if s.order.sale_order_id.startswith("HUB_CONSOLIDATION")]
            print(f"  - Hub consolidation stops: {len(hub_stops)}")
            print(f"  - En-route deliveries: {len(en_route)}")

        return solution


if __name__ == "__main__":
    # Run specific tests
    pytest.main([__file__, "-v", "-s", "-m", "not integration"])
