from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.application.contracts import HistoricalResultItem


class HistoryService:
    def __init__(self, results_dir: str | Path = "results"):
        self.results_dir = Path(results_dir)

    def list_results(self) -> list[HistoricalResultItem]:
        if not self.results_dir.exists():
            return []

        items = []
        for filepath in self.results_dir.glob("routing_result_*.xlsx"):
            stat = filepath.stat()
            items.append(
                HistoricalResultItem(
                    filename=filepath.name,
                    created_at=datetime.fromtimestamp(stat.st_mtime),
                    size_kb=stat.st_size / 1024,
                    path=filepath,
                )
            )

        items.sort(key=lambda item: item.created_at, reverse=True)
        return items
