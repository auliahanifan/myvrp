"""Integration tests for end-to-end workflows."""
import pytest
import tempfile
import os
import shutil
from unittest.mock import patch, MagicMock
import numpy as np

from src.utils.csv_parser import CSVParser
from src.utils.yaml_parser import YAMLParser
from src.utils.distance_calculator import DistanceCalculator
from src.solver.vrp_solver import VRPSolver
from src.output.excel_generator import ExcelGenerator
from src.models.location import Depot


class TestEndToEnd:
    """Test suite for end-to-end workflows."""

    @pytest.fixture
    def temp_test_dir(self):
        """Create temporary directory for test files."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def sample_csv_file(self, temp_test_dir):
        """Create sample CSV file."""
        csv_content = """sale_order_id,delivery_date,delivery_time,load_weight_in_kg,partner_id,display_name,alamat,partner_latitude,partner_longitude,is_priority
ORDER001,2025-10-08,04:00-05:00,50.0,P001,Customer A,Address A,-6.2100,106.8500,false
ORDER002,2025-10-08,05:00-06:00,75.5,P002,Customer B,Address B,-6.2200,106.8600,true
ORDER003,2025-10-08,06:00-07:00,25.0,P003,Customer C,Address C,-6.2300,106.8700,false
ORDER004,2025-10-08,07:00-08:00,40.0,P004,Customer D,Address D,-6.2400,106.8800,false
ORDER005,2025-10-08,08:00-09:00,60.0,P005,Customer E,Address E,-6.2500,106.8900,false"""

        filepath = os.path.join(temp_test_dir, "test_orders.csv")
        with open(filepath, 'w') as f:
            f.write(csv_content)

        return filepath

    @pytest.fixture
    def sample_yaml_file(self, temp_test_dir):
        """Create sample YAML file."""
        yaml_content = """vehicles:
  - name: "L300"
    capacity: 800
    cost_per_km: 5000

  - name: "Granmax"
    capacity: 500
    cost_per_km: 3500

  - name: "Pickup Small"
    capacity: 300
    cost_per_km: 2500

unlimited: true"""

        filepath = os.path.join(temp_test_dir, "test_vehicles.yaml")
        with open(filepath, 'w') as f:
            f.write(yaml_content)

        return filepath

    @pytest.fixture
    def mock_distance_matrix(self):
        """Create mock distance matrix (6x6: depot + 5 customers)."""
        return np.array([
            [0.0,  5.0,  10.0, 15.0, 20.0, 25.0],
            [5.0,  0.0,  6.0,  12.0, 18.0, 24.0],
            [10.0, 6.0,  0.0,  8.0,  14.0, 20.0],
            [15.0, 12.0, 8.0,  0.0,  9.0,  16.0],
            [20.0, 18.0, 14.0, 9.0,  0.0,  10.0],
            [25.0, 24.0, 20.0, 16.0, 10.0, 0.0],
        ])

    @pytest.fixture
    def mock_duration_matrix(self):
        """Create mock duration matrix (6x6: depot + 5 customers)."""
        return np.array([
            [0.0,  10.0, 20.0, 30.0, 40.0, 50.0],
            [10.0, 0.0,  12.0, 25.0, 38.0, 48.0],
            [20.0, 12.0, 0.0,  15.0, 28.0, 40.0],
            [30.0, 25.0, 15.0, 0.0,  18.0, 32.0],
            [40.0, 38.0, 28.0, 18.0, 0.0,  20.0],
            [50.0, 48.0, 40.0, 32.0, 20.0, 0.0],
        ])

    def test_complete_workflow_small_dataset(self, sample_csv_file, sample_yaml_file,
                                            mock_distance_matrix, mock_duration_matrix,
                                            temp_test_dir):
        """Test complete workflow from CSV to Excel output."""

        # Step 1: Parse CSV
        csv_parser = CSVParser(sample_csv_file)
        orders = csv_parser.parse()
        assert len(orders) == 5

        # Step 2: Parse YAML
        yaml_parser = YAMLParser(sample_yaml_file)
        fleet = yaml_parser.parse()
        assert len(fleet.vehicle_types) == 3

        # Step 3: Setup depot
        depot = Depot("Test Depot", (-6.2088, 106.8456), "Test Address")

        # Step 4: Solve VRP (using mock matrices)
        solver = VRPSolver(
            orders=orders,
            fleet=fleet,
            depot=depot,
            distance_matrix=mock_distance_matrix,
            duration_matrix=mock_duration_matrix
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        # Verify solution
        assert solution.total_vehicles_used > 0
        assert solution.total_orders_delivered > 0
        assert solution.total_distance > 0
        assert solution.total_cost > 0

        # Step 5: Generate Excel
        generator = ExcelGenerator(depot=depot)
        excel_path = generator.generate(
            solution=solution,
            output_dir=temp_test_dir,
            filename="test_output.xlsx"
        )

        # Verify Excel file
        assert os.path.exists(excel_path)
        assert excel_path.endswith(".xlsx")

    @patch('src.utils.distance_calculator.googlemaps.Client')
    def test_workflow_with_real_parsers_mock_api(self, mock_google_client,
                                                 sample_csv_file, sample_yaml_file,
                                                 temp_test_dir):
        """Test workflow with real parsers but mocked Google Maps API."""

        # Mock API response
        mock_api_response = {
            "status": "OK",
            "rows": [
                {
                    "elements": [
                        {"status": "OK", "distance": {"value": i * 1000 + j * 500},
                         "duration": {"value": i * 200 + j * 100}}
                        for j in range(6)
                    ]
                }
                for i in range(6)
            ],
        }

        mock_instance = MagicMock()
        mock_instance.distance_matrix.return_value = mock_api_response
        mock_google_client.return_value = mock_instance

        # Parse inputs
        orders = CSVParser(sample_csv_file).parse()
        fleet = YAMLParser(sample_yaml_file).parse()
        depot = Depot("Test Depot", (-6.2088, 106.8456))

        # Calculate distances (will use mock API)
        calculator = DistanceCalculator("mock_api_key", cache_dir=temp_test_dir)
        locations = [depot] + [
            type('obj', (object,), {
                'name': o.display_name,
                'coordinates': o.coordinates,
                'to_tuple': lambda self: self.coordinates
            })()
            for o in orders
        ]

        dist_matrix, dur_matrix = calculator.calculate_matrix(locations)

        # Solve
        solver = VRPSolver(
            orders=orders,
            fleet=fleet,
            depot=depot,
            distance_matrix=dist_matrix,
            duration_matrix=dur_matrix
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        # Generate output
        generator = ExcelGenerator(depot=depot)
        excel_path = generator.generate(
            solution=solution,
            output_dir=temp_test_dir
        )

        assert os.path.exists(excel_path)

    def test_all_optimization_strategies(self, sample_csv_file, sample_yaml_file,
                                        mock_distance_matrix, mock_duration_matrix,
                                        temp_test_dir):
        """Test workflow with all three optimization strategies."""

        strategies = ["minimize_vehicles", "minimize_cost", "balanced"]

        for strategy in strategies:
            # Parse inputs
            orders = CSVParser(sample_csv_file).parse()
            fleet = YAMLParser(sample_yaml_file).parse()
            depot = Depot("Test Depot", (-6.2088, 106.8456))

            # Solve
            solver = VRPSolver(
                orders=orders,
                fleet=fleet,
                depot=depot,
                distance_matrix=mock_distance_matrix,
                duration_matrix=mock_duration_matrix
            )

            solution = solver.solve(optimization_strategy=strategy, time_limit=30)

            # Verify solution has correct strategy
            assert solution.optimization_strategy == strategy
            assert solution.total_vehicles_used > 0

            # Generate Excel
            generator = ExcelGenerator(depot=depot)
            excel_path = generator.generate(
                solution=solution,
                output_dir=temp_test_dir,
                filename=f"output_{strategy}.xlsx"
            )

            assert os.path.exists(excel_path)

    def test_workflow_with_invalid_csv(self, temp_test_dir, sample_yaml_file):
        """Test that workflow handles invalid CSV gracefully."""

        # Create invalid CSV
        invalid_csv = os.path.join(temp_test_dir, "invalid.csv")
        with open(invalid_csv, 'w') as f:
            f.write("invalid,csv,format\n1,2,3")

        # Should raise error during parsing
        parser = CSVParser(invalid_csv)
        with pytest.raises(Exception):  # CSVParserError
            parser.parse()

    def test_workflow_with_single_order(self, temp_test_dir, sample_yaml_file):
        """Test workflow with single order."""

        # Create single-order CSV
        csv_content = """sale_order_id,delivery_date,delivery_time,load_weight_in_kg,partner_id,display_name,alamat,partner_latitude,partner_longitude,is_priority
SINGLE001,2025-10-08,04:00-05:00,50.0,P001,Customer A,Address A,-6.2100,106.8500,false"""

        csv_file = os.path.join(temp_test_dir, "single_order.csv")
        with open(csv_file, 'w') as f:
            f.write(csv_content)

        # Parse
        orders = CSVParser(csv_file).parse()
        fleet = YAMLParser(sample_yaml_file).parse()
        depot = Depot("Test Depot", (-6.2088, 106.8456))

        # 2x2 matrices
        dist_matrix = np.array([[0.0, 5.0], [5.0, 0.0]])
        dur_matrix = np.array([[0.0, 10.0], [10.0, 0.0]])

        # Solve
        solver = VRPSolver(
            orders=orders,
            fleet=fleet,
            depot=depot,
            distance_matrix=dist_matrix,
            duration_matrix=dur_matrix
        )

        solution = solver.solve(optimization_strategy="balanced", time_limit=30)

        # Should use exactly 1 vehicle for 1 order
        assert solution.total_vehicles_used == 1
        assert solution.total_orders_delivered == 1

        # Generate Excel
        generator = ExcelGenerator(depot=depot)
        excel_path = generator.generate(solution=solution, output_dir=temp_test_dir)

        assert os.path.exists(excel_path)
