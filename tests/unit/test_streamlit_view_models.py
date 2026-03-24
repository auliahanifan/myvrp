from __future__ import annotations

from src.presentation.streamlit_view_models import (
    vehicle_editor_rows,
    vehicle_summary_lines,
)


def test_vehicle_editor_rows_expands_motor_into_fragile_and_non_fragile_rows():
    rows = vehicle_editor_rows(
        [
            {
                "name": "Sepeda Motor",
                "capacity": 80.0,
                "cost_per_km": 1500.0,
                "fixed_count": 5,
                "unlimited": False,
            }
        ]
    )

    assert [row["display_name"] for row in rows] == [
        "Sepeda Motor 80 kg (Fragile)",
        "Sepeda Motor 120 kg (Non-Fragile)",
    ]
    assert [row["capacity"] for row in rows] == [80.0, 120.0]
    assert rows[0]["source_index"] == 0
    assert rows[1]["source_index"] == 0
    assert rows[0]["capacity_locked"] is True
    assert rows[1]["capacity_locked"] is True
    assert rows[0]["remove_allowed"] is True
    assert rows[1]["remove_allowed"] is False


def test_vehicle_editor_rows_keeps_non_motor_as_single_editable_row():
    rows = vehicle_editor_rows(
        [
            {
                "name": "Blind Van",
                "capacity": 800.0,
                "cost_per_km": 10000.0,
                "fixed_count": 1,
                "unlimited": False,
            }
        ]
    )

    assert len(rows) == 1
    assert rows[0]["display_name"] == "Blind Van"
    assert rows[0]["capacity"] == 800.0
    assert rows[0]["capacity_locked"] is False


def test_vehicle_summary_lines_uses_same_motor_expansion_as_editor():
    lines = vehicle_summary_lines(
        [
            {
                "name": "Sepeda Motor",
                "capacity": 80.0,
                "cost_per_km": 1500.0,
                "fixed_count": 5,
                "unlimited": True,
            }
        ]
    )

    assert lines == [
        "**Sepeda Motor 80 kg (Fragile)**: 80.0 kg x 5 ♾️",
        "**Sepeda Motor 120 kg (Non-Fragile)**: 120.0 kg x 5 ♾️",
    ]
