"""
Test script for Excel output generation.
Runs a complete VRP solve and generates Excel output.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

from src.utils.csv_parser import CSVParser
from src.utils.yaml_parser import YAMLParser
from src.utils.distance_calculator import DistanceCalculator
from src.solver.vrp_solver import VRPSolver
from src.models.location import Depot, Location
from src.output.excel_generator import ExcelGenerator


def main():
    """Run the test."""
    print("🚀 Starting VRP Excel Output Test...")
    print("=" * 80)

    # Load environment variables
    load_dotenv()
    api_key = os.getenv("RADAR_API_KEY")
    if not api_key:
        print("❌ ERROR: RADAR_API_KEY not found in .env file")
        return

    # Parse inputs
    print("\n📄 Parsing input files...")
    csv_file = "example/example_input.csv"
    yaml_file = "example/example_input_vehicle.yaml"

    try:
        orders = CSVParser(csv_file).parse()
        print(f"   ✅ Parsed {len(orders)} orders from CSV")

        fleet = YAMLParser(yaml_file).parse()
        print(f"   ✅ Parsed fleet with {len(fleet.vehicle_types)} vehicle types")
    except Exception as e:
        print(f"   ❌ Error parsing files: {e}")
        return

    # Setup depot
    depot = Depot(
        name="Segarloka Warehouse",
        coordinates=(-6.2088, 106.8456),
        address="Jakarta, Indonesia"
    )
    print(f"\n🏭 Depot: {depot.name} @ {depot.coordinates}")

    # Calculate distance matrix
    print("\n🗺️  Calculating distance matrix...")
    try:
        calculator = DistanceCalculator(api_key=api_key)
        locations = [depot] + [
            Location(name=o.display_name, coordinates=o.coordinates)
            for o in orders
        ]
        distance_matrix, duration_matrix = calculator.calculate_matrix(locations)
        print(f"   ✅ Distance matrix calculated: {len(distance_matrix)}x{len(distance_matrix[0])}")
    except Exception as e:
        print(f"   ❌ Error calculating distance matrix: {e}")
        return

    # Solve VRP
    print("\n🧮 Solving VRP...")
    strategies = ["minimize_vehicles", "minimize_cost", "balanced"]

    for strategy in strategies:
        print(f"\n   Strategy: {strategy.upper()}")
        print("   " + "-" * 70)

        try:
            solver = VRPSolver(
                orders=orders,
                fleet=fleet,
                depot=depot,
                distance_matrix=distance_matrix,
                duration_matrix=duration_matrix
            )

            solution = solver.solve(
                optimization_strategy=strategy,
                time_limit=300
            )

            print(f"   ✅ Solution found:")
            print(f"      • Vehicles used: {solution.total_vehicles_used}")
            print(f"      • Orders delivered: {solution.total_orders_delivered}")
            print(f"      • Total distance: {solution.total_distance:.2f} km")
            print(f"      • Total cost: Rp {solution.total_cost:,.0f}")
            print(f"      • Computation time: {solution.computation_time:.2f}s")

            # Validate solution
            errors = solution.validate()
            if errors:
                print(f"   ⚠️  Validation warnings:")
                for error in errors[:5]:  # Show first 5 errors
                    print(f"      • {error}")
            else:
                print(f"   ✅ Solution validated successfully")

            # Generate Excel
            print(f"\n   📊 Generating Excel output...")
            try:
                generator = ExcelGenerator(depot=depot)
                filepath = generator.generate(
                    solution=solution,
                    output_dir="results",
                    filename=f"test_routing_{strategy}"
                )
                print(f"   ✅ Excel file generated: {filepath}")
                print(f"      File size: {filepath.stat().st_size:,} bytes")

            except Exception as e:
                print(f"   ❌ Error generating Excel: {e}")
                import traceback
                traceback.print_exc()

        except Exception as e:
            print(f"   ❌ Error solving VRP: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 80)
    print("✅ Test completed! Check the 'results/' folder for Excel files.")


if __name__ == "__main__":
    main()
