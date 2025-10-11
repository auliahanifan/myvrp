"""
Test script to verify that all orders are now included in routing
"""
import tempfile
import os
from pathlib import Path

# Create sample CSV with 10 orders
csv_content = """sale_order_id,delivery_date,delivery_time,load_weight_in_kg,partner_id,display_name,alamat,partner_latitude,partner_longitude,is_priority
SO001,2025-10-11,08:00-09:00,50.5,P001,Customer 1,Address 1,-6.2088,106.8456,1
SO002,2025-10-11,09:00-10:00,30.0,P002,Customer 2,Address 2,-6.2100,106.8500,0
SO003,2025-10-11,08:30-09:30,45.0,P003,Customer 3,Address 3,-6.2150,106.8550,1
SO004,2025-10-11,10:00-11:00,25.0,P004,Customer 4,Address 4,-6.2200,106.8600,0
SO005,2025-10-11,11:00-12:00,35.0,P005,Customer 5,Address 5,-6.2250,106.8650,0
SO006,2025-10-11,08:00-09:00,40.0,P006,Customer 6,Address 6,-6.2300,106.8700,1
SO007,2025-10-11,09:00-10:00,55.0,P007,Customer 7,Address 7,-6.2350,106.8750,0
SO008,2025-10-11,10:00-11:00,20.0,P008,Customer 8,Address 8,-6.2400,106.8800,0
SO009,2025-10-11,11:00-12:00,60.0,P009,Customer 9,Address 9,-6.2450,106.8850,1
SO010,2025-10-11,08:30-09:30,28.0,P010,Customer 10,Address 10,-6.2500,106.8900,0
"""

# Write to temp file
with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
    f.write(csv_content)
    csv_path = f.name

try:
    # Parse CSV
    from src.utils.csv_parser import CSVParser
    parser = CSVParser(csv_path)
    orders = parser.parse()

    print(f"✅ CSV parsed: {len(orders)} orders loaded from CSV")

    # Load fleet config
    from src.utils.yaml_parser import YAMLParser
    fleet_parser = YAMLParser("conf.yaml")
    fleet = fleet_parser.parse()

    print(f"✅ Fleet loaded: {fleet.get_max_vehicles()} vehicles")

    # Create depot
    from src.models.location import Depot, Location
    depot = Depot(
        name="Test Depot",
        coordinates=(-6.2088, 106.8456),
        address="Jakarta"
    )

    # Create locations
    locations = [depot] + [
        Location(o.display_name, o.coordinates, o.alamat)
        for o in orders
    ]

    print(f"✅ Locations created: {len(locations)} locations (depot + {len(orders)} customers)")

    # Calculate distance matrix (using simple Haversine)
    import numpy as np
    from math import radians, cos, sin, asin, sqrt

    def haversine_distance(coord1, coord2):
        """Calculate distance between two coordinates using Haversine formula."""
        lat1, lon1 = coord1
        lat2, lon2 = coord2

        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        r = 6371  # Radius of earth in kilometers
        return c * r

    # Create simple distance matrix (Haversine only, no API)
    distance_matrix = np.zeros((len(locations), len(locations)))
    duration_matrix = np.zeros((len(locations), len(locations)))

    for i in range(len(locations)):
        for j in range(len(locations)):
            if i != j:
                dist = haversine_distance(locations[i].coordinates, locations[j].coordinates)
                distance_matrix[i][j] = dist
                # Assume 30 km/h average speed
                duration_matrix[i][j] = (dist / 30.0) * 60  # minutes

    print(f"✅ Distance matrix calculated: {distance_matrix.shape}")

    # Solve VRP
    from src.solver.vrp_solver import VRPSolver
    solver = VRPSolver(
        orders=orders,
        fleet=fleet,
        depot=depot,
        distance_matrix=distance_matrix,
        duration_matrix=duration_matrix
    )

    print(f"\n🔄 Solving VRP...")
    solution = solver.solve(optimization_strategy="balanced", time_limit=30)

    print(f"\n📊 SOLUTION RESULTS:")
    print(f"   Input orders: {len(orders)}")
    print(f"   Orders delivered: {solution.total_orders_delivered}")
    print(f"   Unassigned orders: {len(solution.unassigned_orders)}")
    print(f"   Vehicles used: {solution.total_vehicles_used}")
    print(f"   Total distance: {solution.total_distance:.2f} km")

    # Check if all orders are assigned
    if solution.total_orders_delivered == len(orders):
        print(f"\n✅ SUCCESS! All {len(orders)} orders are included in routing!")
    else:
        print(f"\n❌ PROBLEM! Only {solution.total_orders_delivered}/{len(orders)} orders were assigned")
        if solution.unassigned_orders:
            print(f"\n   Unassigned orders:")
            for order in solution.unassigned_orders:
                print(f"   - {order.sale_order_id}: {order.display_name}")

    # Show routes
    print(f"\n📋 ROUTES:")
    for i, route in enumerate(solution.routes):
        if route.num_stops > 0:
            print(f"   Route {i+1} ({route.vehicle.name}): {route.num_stops} stops, {route.total_distance:.2f} km")
            for stop in route.stops:
                print(f"      - {stop.order.sale_order_id}: {stop.order.display_name}")

finally:
    # Cleanup
    os.unlink(csv_path)
    print(f"\n🧹 Cleanup complete")
