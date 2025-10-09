#!/usr/bin/env python3
"""
Verification script for Phase 1 completion.
Tests that all components can be imported and basic functionality works.
"""

def test_imports():
    """Test that all modules can be imported."""
    print("🔍 Testing imports...")

    try:
        from src.models.order import Order
        from src.models.vehicle import Vehicle, VehicleFleet
        from src.models.route import Route, RouteStop, RoutingSolution
        from src.models.location import Location, Depot
        from src.utils.csv_parser import CSVParser
        from src.utils.yaml_parser import YAMLParser
        from src.utils.distance_calculator import DistanceCalculator
        from src.solver.vrp_solver import VRPSolver
        print("✅ All imports successful")
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False


def test_models():
    """Test that models can be instantiated."""
    print("\n🔍 Testing models...")

    try:
        from src.models.order import Order
        from src.models.vehicle import Vehicle, VehicleFleet
        from src.models.location import Depot

        # Test Order
        order = Order(
            sale_order_id="TEST001",
            delivery_date="2025-10-10",
            delivery_time="08:00",
            load_weight_in_kg=25.5,
            partner_id="C001",
            display_name="Test Customer",
            alamat="Test Address",
            coordinates=(-6.2088, 106.8456),
            is_priority=False
        )
        print(f"✅ Order model: {order}")

        # Test Vehicle
        vehicle = Vehicle(name="L300", capacity=800, cost_per_km=5000)
        print(f"✅ Vehicle model: {vehicle}")

        # Test VehicleFleet
        fleet = VehicleFleet(vehicle_types=[vehicle], unlimited=True)
        print(f"✅ VehicleFleet model: {fleet}")

        # Test Depot
        depot = Depot("Test Depot", (-6.2088, 106.8456))
        print(f"✅ Depot model: {depot}")

        return True
    except Exception as e:
        print(f"❌ Model test failed: {e}")
        return False


def test_parsers():
    """Test that parsers can parse example files."""
    print("\n🔍 Testing parsers...")

    try:
        from src.utils.csv_parser import CSVParser
        from src.utils.yaml_parser import YAMLParser

        # Test CSV Parser
        csv_parser = CSVParser("example/example_input.csv")
        orders = csv_parser.parse()
        print(f"✅ CSV Parser: Loaded {len(orders)} orders")
        for order in orders[:2]:  # Show first 2
            print(f"   - {order}")

        # Test YAML Parser
        yaml_parser = YAMLParser("example/example_input_vehicle.yaml")
        fleet = yaml_parser.parse()
        print(f"✅ YAML Parser: Loaded {len(fleet)} vehicle types")
        for i in range(min(len(fleet), 2)):  # Show first 2
            vehicle = fleet.get_vehicle_by_index(i)
            print(f"   - {vehicle}")

        return True
    except Exception as e:
        print(f"❌ Parser test failed: {e}")
        return False


def test_validation():
    """Test that validation works correctly."""
    print("\n🔍 Testing validation...")

    try:
        from src.models.order import Order

        # Test invalid coordinates
        try:
            invalid_order = Order(
                sale_order_id="INVALID",
                delivery_date="2025-10-10",
                delivery_time="08:00",
                load_weight_in_kg=25.5,
                partner_id="C001",
                display_name="Invalid",
                alamat="Test",
                coordinates=(200, 200),  # Invalid lat/lng
            )
            print("❌ Validation failed: Should reject invalid coordinates")
            return False
        except ValueError:
            print("✅ Validation working: Rejected invalid coordinates")

        # Test invalid weight
        try:
            invalid_order = Order(
                sale_order_id="INVALID",
                delivery_date="2025-10-10",
                delivery_time="08:00",
                load_weight_in_kg=-10,  # Negative weight
                partner_id="C001",
                display_name="Invalid",
                alamat="Test",
                coordinates=(-6.2088, 106.8456),
            )
            print("❌ Validation failed: Should reject negative weight")
            return False
        except ValueError:
            print("✅ Validation working: Rejected negative weight")

        return True
    except Exception as e:
        print(f"❌ Validation test failed: {e}")
        return False


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("🚀 Phase 1 Verification Script")
    print("=" * 60)

    results = []

    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Models", test_models()))
    results.append(("Parsers", test_parsers()))
    results.append(("Validation", test_validation()))

    # Summary
    print("\n" + "=" * 60)
    print("📊 Verification Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 Phase 1 Verification: ALL TESTS PASSED")
        print("✅ Ready for Phase 2 development!")
    else:
        print("❌ Phase 1 Verification: SOME TESTS FAILED")
        print("⚠️  Please check the errors above")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
