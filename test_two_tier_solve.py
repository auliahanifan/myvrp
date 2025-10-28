"""
Comprehensive test for two-tier solver solve() method.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.models.order import Order
from src.models.location import Depot, Hub
from src.utils.yaml_parser import YAMLParser
from src.utils.hub_routing import HubRoutingManager
from src.solver.two_tier_vrp_solver import TwoTierVRPSolver
import numpy as np


def test_two_tier_solve():
    """Test two-tier solver solve() method."""
    print("=" * 70)
    print("COMPREHENSIVE TEST: Two-Tier VRP Solver with solve()")
    print("=" * 70)

    # Load configuration
    parser = YAMLParser("conf.yaml")
    fleet = parser.parse()
    hub_config = parser.get_hub_config()

    if not hub_config:
        print("❌ Hub configuration not enabled")
        return False

    # Create depot and hub
    depot = Depot(
        name="Main Depot",
        coordinates=(-6.2088, 106.8456),
        address="Jakarta"
    )

    hub = hub_config["hub"]

    # Create realistic test orders
    orders = [
        Order(
            sale_order_id="ORD001",
            delivery_date="2025-10-28",
            delivery_time="08:00-09:00",
            load_weight_in_kg=5.0,
            partner_id="CUST001",
            display_name="Customer 1 - JakUt",
            alamat="Jl. Utama No.1",
            coordinates=(-6.15, 106.87),
            kota="JAKARTA UTARA",
            is_priority=False
        ),
        Order(
            sale_order_id="ORD002",
            delivery_date="2025-10-28",
            delivery_time="10:00-11:00",
            load_weight_in_kg=8.0,
            partner_id="CUST002",
            display_name="Customer 2 - Tangerang",
            alamat="Jl. Raya No.2",
            coordinates=(-6.18, 106.65),
            kota="TANGERANG",
            is_priority=False
        ),
        Order(
            sale_order_id="ORD003",
            delivery_date="2025-10-28",
            delivery_time="14:00-15:00",
            load_weight_in_kg=3.0,
            partner_id="CUST003",
            display_name="Customer 3 - Bekasi",
            alamat="Jl. Industri No.3",
            coordinates=(-6.22, 107.00),
            kota="BEKASI",
            is_priority=False
        ),
        Order(
            sale_order_id="ORD004",
            delivery_date="2025-10-28",
            delivery_time="09:00-10:00",
            load_weight_in_kg=10.0,
            partner_id="CUST004",
            display_name="Customer 4 - JakBar",
            alamat="Jl. Sunset No.4",
            coordinates=(-6.20, 106.75),
            kota="JAKARTA BARAT",
            is_priority=True
        ),
    ]

    # Create hub manager
    hub_manager = HubRoutingManager(
        hub=hub,
        depot=depot,
        zones_via_hub=hub_config.get("zones_via_hub", []),
        blind_van_arrival_time=hub_config.get("blind_van_arrival", 360),
        motor_start_time=hub_config.get("motor_start_time", 360),
    )

    # Show classification
    hub_orders, direct_orders = hub_manager.classify_orders(orders)
    print(f"\n📋 Order Classification:")
    print(f"   Hub Orders ({len(hub_orders)}):")
    for o in hub_orders:
        print(f"     - {o.sale_order_id}: {o.display_name} ({o.kota}) - {o.load_weight_in_kg}kg")
    print(f"   Direct Orders ({len(direct_orders)}):")
    for o in direct_orders:
        print(f"     - {o.sale_order_id}: {o.display_name} ({o.kota}) - {o.load_weight_in_kg}kg")

    # Create realistic distance matrix
    # Indices: 0=DEPOT, 1=HUB, 2=ORD001, 3=ORD002, 4=ORD003, 5=ORD004
    n_locations = 2 + len(orders)  # DEPOT + HUB + customers
    distance_matrix = np.array([
        # DEPOT  HUB   ORD1  ORD2  ORD3  ORD4
        [0,     5,    8,    15,   22,   10],    # DEPOT
        [5,     0,    3,    10,   20,   5],     # HUB
        [8,     3,    0,    12,   25,   10],    # ORD001 (JakUt)
        [15,    10,   12,   0,    15,   5],     # ORD002 (Tangerang)
        [22,    20,   25,   15,   0,    25],    # ORD003 (Bekasi)
        [10,    5,    10,   5,    25,   0],     # ORD004 (JakBar)
    ], dtype=float)

    duration_matrix = distance_matrix * 2  # Assume 2 min/km
    duration_matrix[0, 1] = 10  # DEPOT->HUB takes 10 min
    duration_matrix[1, 0] = 10  # HUB->DEPOT takes 10 min

    print(f"\n📊 Distance Matrix: {distance_matrix.shape}")
    print(f"   Locations: 0=DEPOT, 1=HUB, 2+=customers")

    # Test two-tier solver
    print(f"\n🧪 Testing TwoTierVRPSolver.solve()...")
    try:
        solver = TwoTierVRPSolver(
            orders=orders,
            fleet=fleet,
            depot=depot,
            hub=hub,
            hub_manager=hub_manager,
            full_distance_matrix=distance_matrix,
            full_duration_matrix=duration_matrix,
        )

        print(f"\n🚀 Calling solve()...")
        solution = solver.solve(
            optimization_strategy="balanced",
            time_limit=60,
        )

        print(f"\n✅ SOLUTION FOUND!")
        print(f"   Total Routes: {len(solution.routes)}")
        print(f"   Total Delivered: {solution.total_orders_delivered}")
        print(f"   Total Distance: {solution.total_distance:.1f} km")
        print(f"   Total Cost: Rp {solution.total_cost:,.0f}")

        # Show routes
        print(f"\n📍 Routes:")
        for i, route in enumerate(solution.routes, 1):
            vehicle_name = route.vehicle.name if route.vehicle else "Unknown"
            print(f"\n   Route {i}: {vehicle_name}")
            print(f"   Departure: {route.departure_time} min")
            print(f"   Distance: {route.total_distance:.1f} km")
            print(f"   Weight: {route.total_weight:.1f} kg")
            print(f"   Stops:")
            for stop in route.stops:
                print(f"      - {stop.order.sale_order_id}: {stop.order.display_name} @ {stop.arrival_time} min")

        # Check for unassigned
        if solution.unassigned_orders:
            print(f"\n⚠️  Unassigned Orders ({len(solution.unassigned_orders)}):")
            for order in solution.unassigned_orders:
                print(f"   - {order.sale_order_id}: {order.display_name}")
        else:
            print(f"\n✅ All orders assigned!")

        return True

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        if test_two_tier_solve():
            print("\n" + "=" * 70)
            print("✅ Two-Tier Solver Works Perfectly!")
            print("=" * 70)
            sys.exit(0)
        else:
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
