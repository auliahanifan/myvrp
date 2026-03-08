from src.models.vehicle import Vehicle, VehicleFleet


def test_legacy_vehicle_fleet_cycles_overflow_vehicle_types_when_unlimited():
    fleet = VehicleFleet(
        vehicle_types=[
            Vehicle(name="L300", capacity=800, cost_per_km=5000),
            Vehicle(name="Granmax", capacity=500, cost_per_km=3500),
            Vehicle(name="Pickup", capacity=300, cost_per_km=2500),
        ],
        unlimited=True,
    )

    overflow_names = [
        fleet.get_vehicle_by_index(3).name,
        fleet.get_vehicle_by_index(4).name,
        fleet.get_vehicle_by_index(5).name,
    ]

    assert overflow_names == ["L300_3", "Granmax_4", "Pickup_5"]
