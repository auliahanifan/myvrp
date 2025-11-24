"""
Test script to verify vehicle naming fix for two-tier routing.
Checks that all vehicle names are unique across HUB and DEPOT routes using prefixes.
"""
from src.models.vehicle import Vehicle, VehicleFleet

def test_vehicle_prefix_naming():
    """Test that HUB and DEPOT prefixes make vehicle names unique."""

    # Create a simple vehicle type
    city_car = Vehicle(
        name="City Car 250kg",
        capacity=250,
        cost_per_km=4000,
    )

    # Create fleet
    fleet = VehicleFleet(
        vehicle_types=[(city_car, 3, False)],
    )

    # Simulate Tier 2a (HUB) - vehicles start from 0
    vehicles_hub = fleet.get_all_vehicles(start_id=0)
    print("Tier 2a (HUB) vehicles before prefix:")
    for v in vehicles_hub:
        print(f"  - {v.name} (ID: {v.vehicle_id})")

    # Add HUB- prefix (simulating what two_tier_vrp_solver does)
    for v in vehicles_hub:
        v.name = f"HUB-{v.name}"

    print("\nTier 2a (HUB) vehicles after prefix:")
    hub_names = []
    for v in vehicles_hub:
        print(f"  - {v.name} (ID: {v.vehicle_id})")
        hub_names.append(v.name)

    # Simulate Tier 2b (DEPOT) - vehicles also start from 0 (same fleet config)
    vehicles_depot = fleet.get_all_vehicles(start_id=0)
    print("\nTier 2b (DEPOT) vehicles before prefix:")
    for v in vehicles_depot:
        print(f"  - {v.name} (ID: {v.vehicle_id})")

    # Add DEPOT- prefix (simulating what two_tier_vrp_solver does)
    for v in vehicles_depot:
        v.name = f"DEPOT-{v.name}"

    print("\nTier 2b (DEPOT) vehicles after prefix:")
    depot_names = []
    for v in vehicles_depot:
        print(f"  - {v.name} (ID: {v.vehicle_id})")
        depot_names.append(v.name)

    # Test: Verify no duplicates
    all_names = hub_names + depot_names
    unique_names = set(all_names)

    print(f"\n✅ All vehicle names: {all_names}")
    print(f"✅ Unique names: {len(unique_names)} out of {len(all_names)}")

    # Check for duplicates
    if len(unique_names) != len(all_names):
        duplicates = len(all_names) - len(unique_names)
        raise AssertionError(f"❌ FAILED: Found {duplicates} duplicate vehicle names!")

    # Verify expected naming pattern
    expected_hub = ["HUB-City Car 250kg_0", "HUB-City Car 250kg_1", "HUB-City Car 250kg_2"]
    expected_depot = ["DEPOT-City Car 250kg_0", "DEPOT-City Car 250kg_1", "DEPOT-City Car 250kg_2"]

    assert hub_names == expected_hub, f"HUB names mismatch: {hub_names}"
    assert depot_names == expected_depot, f"DEPOT names mismatch: {depot_names}"

    print("\n✅ TEST PASSED: Vehicle names are unique with HUB-/DEPOT- prefixes!")

if __name__ == "__main__":
    test_vehicle_prefix_naming()
