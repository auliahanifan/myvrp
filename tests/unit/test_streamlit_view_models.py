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
                "max_capacity": 135.0,
                "cost_per_km": 1500.0,
                "fixed_count": 5,
                "unlimited": False,
            }
        ]
    )

    assert len(rows) == 1
    assert rows[0]["display_name"] == "Sepeda Motor"
    assert rows[0]["capacity"] == 80.0
    assert rows[0]["max_capacity"] == 135.0
    assert rows[0]["source_index"] == 0
    assert rows[0]["is_motor"] is True


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
    assert rows[0]["max_capacity"] is None
    assert rows[0]["is_motor"] is False


def test_vehicle_summary_lines_uses_same_motor_expansion_as_editor():
    lines = vehicle_summary_lines(
        [
            {
                "name": "Sepeda Motor",
                "capacity": 80.0,
                "max_capacity": 140.0,
                "cost_per_km": 1500.0,
                "fixed_count": 5,
                "unlimited": True,
            }
        ]
    )

    assert lines == [
        "**Sepeda Motor**: normal 80.0 kg / max 140.0 kg x 5 ♾️",
    ]
