from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.application.contracts import MapRenderRequest, MapRenderResult
from src.visualization.map_visualizer import MapVisualizer


class MapService:
    def __init__(
        self,
        visualizer_cls=MapVisualizer,
        results_dir: str | Path = "results",
        now_provider=datetime.now,
    ):
        self.visualizer_cls = visualizer_cls
        self.results_dir = Path(results_dir)
        self.now_provider = now_provider

    def render_map_html(self, request: MapRenderRequest) -> MapRenderResult:
        visualizer = self.visualizer_cls(
            depot=request.depot,
            hubs_config=request.hubs_config,
            enable_road_routing=True,
        )

        if request.selected_route_index is None:
            route_map = visualizer.create_map(request.solution, zoom_start=12)
        else:
            route_map = visualizer.create_single_route_map(
                request.solution,
                request.selected_route_index,
                zoom_start=12,
            )

        return MapRenderResult(
            html=route_map._repr_html_(),
            cache_key=request.cache_key,
            generated_with_road_routing=visualizer.enable_road_routing,
        )

    def save_map_html(
        self,
        html: str,
        selected_route_index: int | None,
    ) -> Path:
        self.results_dir.mkdir(parents=True, exist_ok=True)
        timestamp = self.now_provider().strftime("%Y%m%d_%H%M%S")
        if selected_route_index is None:
            filename = f"route_map_all_{timestamp}.html"
        else:
            filename = f"route_map_vehicle{selected_route_index + 1}_{timestamp}.html"

        output_path = self.results_dir / filename
        output_path.write_text(html, encoding="utf-8")
        return output_path
