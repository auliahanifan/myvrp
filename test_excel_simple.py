"""
Simple test for Excel generation with mock data.
"""
from datetime import datetime

from src.models.order import Order
from src.models.vehicle import Vehicle, VehicleFleet
from src.models.route import Route, RouteStop, RoutingSolution
from src.models.location import Depot
from src.output.excel_generator import ExcelGenerator


def create_mock_solution() -> RoutingSolution:
    """Create a mock routing solution for testing."""

    # Create vehicles
    vehicle1 = Vehicle(name="L300_0", capacity=150, cost_per_km=5000, vehicle_id=0)
    vehicle2 = Vehicle(name="Granmax_1", capacity=250, cost_per_km=6000, vehicle_id=1)

    # Create orders
    orders = [
        Order(
            sale_order_id="SO001",
            delivery_date="2025-10-10",
            delivery_time="04:30",
            load_weight_in_kg=25.5,
            partner_id="P001",
            display_name="Restaurant A",
            alamat="Jl. Sudirman No. 123, Jakarta",
            coordinates=(-6.2088, 106.8456),
            is_priority=True
        ),
        Order(
            sale_order_id="SO002",
            delivery_date="2025-10-10",
            delivery_time="05:00",
            load_weight_in_kg=30.0,
            partner_id="P002",
            display_name="Restaurant B",
            alamat="Jl. Thamrin No. 456, Jakarta",
            coordinates=(-6.1951, 106.8230),
            is_priority=False
        ),
        Order(
            sale_order_id="SO003",
            delivery_date="2025-10-10",
            delivery_time="05:30",
            load_weight_in_kg=15.0,
            partner_id="P003",
            display_name="Restaurant C",
            alamat="Jl. Gatot Subroto No. 789, Jakarta",
            coordinates=(-6.2297, 106.8311),
            is_priority=False
        ),
        Order(
            sale_order_id="SO004",
            delivery_date="2025-10-10",
            delivery_time="06:00",
            load_weight_in_kg=40.0,
            partner_id="P004",
            display_name="Restaurant D",
            alamat="Jl. Rasuna Said No. 101, Jakarta",
            coordinates=(-6.2238, 106.8412),
            is_priority=True
        ),
    ]

    # Create Route 1 (vehicle1 with 2 stops)
    route1 = Route(
        vehicle=vehicle1,
        departure_time=240  # 04:00
    )

    stop1 = RouteStop(
        order=orders[0],
        arrival_time=270,  # 04:30
        departure_time=285,  # 04:45
        distance_from_prev=5.2,
        cumulative_weight=25.5,
        sequence=1
    )
    route1.add_stop(stop1)

    stop2 = RouteStop(
        order=orders[1],
        arrival_time=300,  # 05:00
        departure_time=315,  # 05:15
        distance_from_prev=3.8,
        cumulative_weight=55.5,
        sequence=2
    )
    route1.add_stop(stop2)

    route1.calculate_metrics()

    # Create Route 2 (vehicle2 with 2 stops)
    route2 = Route(
        vehicle=vehicle2,
        departure_time=300  # 05:00
    )

    stop3 = RouteStop(
        order=orders[2],
        arrival_time=330,  # 05:30
        departure_time=345,  # 05:45
        distance_from_prev=4.5,
        cumulative_weight=15.0,
        sequence=1
    )
    route2.add_stop(stop3)

    stop4 = RouteStop(
        order=orders[3],
        arrival_time=360,  # 06:00
        departure_time=375,  # 06:15
        distance_from_prev=2.3,
        cumulative_weight=55.0,
        sequence=2
    )
    route2.add_stop(stop4)

    route2.calculate_metrics()

    # Create solution
    solution = RoutingSolution(
        routes=[route1, route2],
        unassigned_orders=[],
        optimization_strategy="balanced",
        computation_time=12.45
    )

    return solution


def main():
    """Run the test."""
    print("🧪 Testing Excel Generator with Mock Data...")
    print("=" * 80)

    # Create depot
    depot = Depot(
        name="Segarloka Warehouse",
        coordinates=(-6.2088, 106.8456),
        address="Jakarta, Indonesia"
    )

    # Create mock solution
    print("\n📊 Creating mock routing solution...")
    solution = create_mock_solution()

    print(f"   ✅ Solution created:")
    print(f"      • Vehicles: {solution.total_vehicles_used}")
    print(f"      • Orders: {solution.total_orders_delivered}")
    print(f"      • Distance: {solution.total_distance:.2f} km")
    print(f"      • Cost: Rp {solution.total_cost:,.0f}")

    # Validate
    print(f"\n✅ Validating solution...")
    errors = solution.validate()
    if errors:
        print(f"   ⚠️  Validation errors:")
        for error in errors:
            print(f"      • {error}")
    else:
        print(f"   ✅ No validation errors")

    # Generate Excel
    print(f"\n📝 Generating Excel output...")
    try:
        generator = ExcelGenerator(depot=depot)
        filepath = generator.generate(
            solution=solution,
            output_dir="results",
            filename="test_mock_data"
        )
        print(f"   ✅ Excel file generated successfully!")
        print(f"      Path: {filepath}")
        print(f"      Size: {filepath.stat().st_size:,} bytes")

        # List files in results directory
        print(f"\n📁 Files in results directory:")
        from pathlib import Path
        results_dir = Path("results")
        if results_dir.exists():
            for file in sorted(results_dir.glob("*.xlsx"), key=lambda x: x.stat().st_mtime, reverse=True):
                size = file.stat().st_size
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                print(f"      • {file.name} ({size:,} bytes) - {mtime.strftime('%Y-%m-%d %H:%M:%S')}")

    except Exception as e:
        print(f"   ❌ Error generating Excel: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("\n" + "=" * 80)
    print("✅ Excel generation test PASSED!")
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
