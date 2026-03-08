from __future__ import annotations

import tempfile
from io import BytesIO
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.application.configuration_service import ConfigurationService
from src.application.contracts import (
    AppConfigSnapshot,
    RoutePlanSummary,
    RoutePlanningRequest,
    RoutePlanningResult,
    UploadOrdersResult,
)
from src.models.location import Location
from src.output.csv_generator import CSVGenerator
from src.output.excel_generator import ExcelGenerator
from src.solver.two_tier_vrp_solver import MultiHubVRPSolver
from src.utils.csv_parser import CSVParser
from src.utils.distance_calculator import DistanceCalculator
from src.utils.hub_routing import MultiHubRoutingManager
from src.utils.yaml_parser import YAMLParser


class RoutePlanningService:
    def __init__(
        self,
        csv_parser_cls=CSVParser,
        yaml_parser_cls=YAMLParser,
        distance_calculator_cls=DistanceCalculator,
        routing_manager_factory=MultiHubRoutingManager,
        solver_factory=MultiHubVRPSolver,
        excel_generator_cls=ExcelGenerator,
        csv_generator_cls=CSVGenerator,
        configuration_service: ConfigurationService | None = None,
        now_provider=datetime.now,
        results_dir: str | Path = "results",
    ):
        self.csv_parser_cls = csv_parser_cls
        self.yaml_parser_cls = yaml_parser_cls
        self.distance_calculator_cls = distance_calculator_cls
        self.routing_manager_factory = routing_manager_factory
        self.solver_factory = solver_factory
        self.excel_generator_cls = excel_generator_cls
        self.csv_generator_cls = csv_generator_cls
        self.configuration_service = configuration_service or ConfigurationService(
            yaml_parser_cls=yaml_parser_cls
        )
        self.now_provider = now_provider
        self.results_dir = Path(results_dir)

    def parse_uploaded_orders(
        self, orders_file_bytes: bytes, orders_filename: str
    ) -> UploadOrdersResult:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(orders_filename).suffix or ".csv") as tmp_file:
            tmp_file.write(orders_file_bytes)
            tmp_path = tmp_file.name

        try:
            parser = self.csv_parser_cls(tmp_path)
            orders = parser.parse()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        preview_df = pd.read_csv(BytesIO(orders_file_bytes))

        return UploadOrdersResult(
            orders=orders,
            preview_rows=preview_df.head(10).to_dict(orient="records"),
            total_orders=len(orders),
            total_weight_kg=sum(order.load_weight_in_kg for order in orders),
            priority_orders=sum(1 for order in orders if order.is_priority),
        )

    def plan(
        self,
        request: RoutePlanningRequest,
        config_snapshot: AppConfigSnapshot,
    ) -> RoutePlanningResult:
        upload_result = self.parse_uploaded_orders(
            request.orders_file_bytes,
            request.orders_filename,
        )
        fleet = config_snapshot.fleet
        if request.vehicle_config.get("vehicles"):
            fleet = self.configuration_service.config_dict_to_fleet(request.vehicle_config)

        hub_routing_manager = self.routing_manager_factory(
            config_snapshot.hubs_config,
            config_snapshot.depot,
        )

        locations = [config_snapshot.depot]
        if not config_snapshot.hubs_config.is_zero_hub_mode:
            locations.extend(hub_config.hub for hub_config in config_snapshot.hubs_config.hubs)
        locations.extend(
            Location(order.display_name, order.coordinates, order.alamat)
            for order in upload_result.orders
        )

        cache_config = config_snapshot.cache_config
        calculator = self.distance_calculator_cls(
            cache_dir=cache_config.get("directory", ".cache"),
            cache_ttl_hours=cache_config.get("ttl_hours", 24),
            enable_cache=cache_config.get("enabled", True),
        )
        distance_matrix, duration_matrix = calculator.calculate_matrix(locations)

        solver = self.solver_factory(
            orders=upload_result.orders,
            fleet=fleet,
            depot=config_snapshot.depot,
            multi_hub_config=config_snapshot.hubs_config,
            hub_routing_manager=hub_routing_manager,
            full_distance_matrix=distance_matrix,
            full_duration_matrix=duration_matrix,
            config=config_snapshot.solver_config,
        )
        solution = solver.solve(
            optimization_strategy=request.optimization_strategy,
            time_limit=request.time_limit_seconds,
        )

        self.results_dir.mkdir(parents=True, exist_ok=True)
        timestamp = self.now_provider().strftime("%Y-%m-%d_%H-%M-%S")
        excel_path = self.excel_generator_cls(depot=config_snapshot.depot).generate(
            solution=solution,
            output_dir=str(self.results_dir),
        )
        csv_generator = self.csv_generator_cls(
            depot=config_snapshot.depot,
            hubs_config=config_snapshot.hubs_config,
        )
        csv_path = csv_generator.generate(
            solution=solution,
            output_dir=str(self.results_dir),
            filename=f"routing_result_{timestamp}",
        )
        csv_summary_path = csv_generator.generate_summary_csv(
            solution=solution,
            output_dir=str(self.results_dir),
            filename=f"routing_summary_{timestamp}",
        )

        if config_snapshot.hubs_config.is_zero_hub_mode:
            hub_summary = {
                "total_hub_orders": 0,
                "direct_orders_count": len(upload_result.orders),
                "hub_percentage": 0.0,
            }
        else:
            hub_summary = hub_routing_manager.get_routing_summary(upload_result.orders)

        summary = RoutePlanSummary(
            total_vehicles=solution.total_vehicles_used,
            total_orders=solution.total_orders_delivered,
            total_distance_km=solution.total_distance,
            total_cost=solution.total_cost,
            computation_time_seconds=solution.computation_time,
            optimization_strategy=solution.optimization_strategy,
            unassigned_orders=len(solution.unassigned_orders),
        )

        return RoutePlanningResult(
            solution=solution,
            summary=summary,
            excel_path=Path(excel_path) if excel_path is not None else None,
            csv_path=Path(csv_path) if csv_path is not None else None,
            csv_summary_path=Path(csv_summary_path) if csv_summary_path is not None else None,
            hub_summary=hub_summary,
            depot=config_snapshot.depot,
            hubs_config=config_snapshot.hubs_config,
            map_cache_seed=timestamp,
        )
