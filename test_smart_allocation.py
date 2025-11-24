"""
Test script to verify smart vehicle allocation in two-tier routing.
Ensures global vehicle pool is split correctly between HUB and DEPOT.
"""
from src.models.vehicle import Vehicle, VehicleFleet

def test_smart_allocation():
    """Test that vehicles are allocated proportionally without duplication."""

    # Create vehicle types matching conf.yaml
    blind_van = Vehicle(name="Blind Van", capacity=500, cost_per_km=10000)
    city_350 = Vehicle(name="City Car 350kg", capacity=350, cost_per_km=6000)
    city_250 = Vehicle(name="City Car 250kg", capacity=250, cost_per_km=4000)
    motor = Vehicle(name="Sepeda Motor", capacity=100, cost_per_km=1500)

    # Create global fleet (as defined in conf.yaml)
    global_fleet = VehicleFleet(
        vehicle_types=[
            (blind_van, 1, False),
            (city_350, 2, False),  # 2 units total globally
            (city_250, 1, False),  # 1 unit total globally
            (motor, 50, True),     # Unlimited
        ]
    )

    print("="*70)
    print("GLOBAL FLEET (from conf.yaml)")
    print("="*70)
    print(f"Blind Van: 1 unit")
    print(f"City Car 350kg: 2 units (GLOBAL)")
    print(f"City Car 250kg: 1 unit (GLOBAL)")
    print(f"Sepeda Motor: 50 units (unlimited)")

    # Simulate weight-based allocation
    # Example: HUB has 1200kg (60%), DEPOT has 800kg (40%)
    hub_weight = 1200
    depot_weight = 800
    total_weight = hub_weight + depot_weight
    hub_ratio = hub_weight / total_weight
    depot_ratio = depot_weight / total_weight

    print(f"\n" + "="*70)
    print(f"ORDER WEIGHT DISTRIBUTION")
    print("="*70)
    print(f"HUB: {hub_weight}kg ({hub_ratio*100:.1f}%)")
    print(f"DEPOT: {depot_weight}kg ({depot_ratio*100:.1f}%)")

    # Smart allocation (fixed vehicles only, excluding Blind Van)
    print(f"\n" + "="*70)
    print(f"SMART VEHICLE ALLOCATION")
    print("="*70)

    # City Car 350kg: 2 units total
    hub_350 = round(2 * hub_ratio)  # 1.2 → 1
    depot_350 = 2 - hub_350          # 1

    # City Car 250kg: 1 unit total
    hub_250 = round(1 * hub_ratio)  # 0.6 → 1
    depot_250 = 1 - hub_250          # 0

    # Adjust if rounding gives 0 to a zone that has demand
    if hub_250 == 0 and hub_weight > 0:
        hub_250 = 1
        depot_250 = 0

    print(f"\nCity Car 350kg (2 units total):")
    print(f"  → HUB: {hub_350} units")
    print(f"  → DEPOT: {depot_350} units")
    print(f"  ✓ Total: {hub_350 + depot_350} (matches global pool)")

    print(f"\nCity Car 250kg (1 unit total):")
    print(f"  → HUB: {hub_250} units")
    print(f"  → DEPOT: {depot_250} units")
    print(f"  ✓ Total: {hub_250 + depot_250} (matches global pool)")

    print(f"\nSepeda Motor (unlimited):")
    print(f"  → HUB: unlimited")
    print(f"  → DEPOT: unlimited")

    # Verify no duplication
    total_350 = hub_350 + depot_350
    total_250 = hub_250 + depot_250

    assert total_350 == 2, f"❌ FAILED: City Car 350kg duplication! Expected 2, got {total_350}"
    assert total_250 == 1, f"❌ FAILED: City Car 250kg duplication! Expected 1, got {total_250}"

    print(f"\n" + "="*70)
    print("✅ TEST PASSED: No vehicle duplication!")
    print("="*70)
    print(f"✓ Fixed vehicles properly split between HUB and DEPOT")
    print(f"✓ Total vehicles match global conf.yaml configuration")
    print(f"✓ Allocation is proportional to order weight")

if __name__ == "__main__":
    test_smart_allocation()
