from __future__ import annotations

from typing import Any

import pandas as pd


MOTOR_FRAGILE_CAPACITY_KG = 80.0
MOTOR_NON_FRAGILE_CAPACITY_KG = 120.0


def preview_dataframe(preview_rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not preview_rows:
        return pd.DataFrame()
    return pd.DataFrame(preview_rows)


def records_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def vehicle_editor_rows(vehicles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for idx, vehicle in enumerate(vehicles):
        rows.append(
            {
                "display_key": str(idx),
                "source_index": idx,
                "display_name": vehicle["name"],
                "capacity": float(vehicle["capacity"]),
                "max_capacity": _motor_max_capacity(vehicle),
                "is_motor": _is_motor_vehicle(vehicle),
                "capacity_locked": False,
                "remove_allowed": True,
            }
        )

    return rows


def vehicle_summary_lines(vehicles: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []

    for row in vehicle_editor_rows(vehicles):
        source_vehicle = vehicles[row["source_index"]]
        unlimited = " ♾️" if source_vehicle.get("unlimited", False) else ""
        if row["is_motor"]:
            lines.append(
                f"**{row['display_name']}**: normal {row['capacity']} kg / max "
                f"{row['max_capacity']} kg x {source_vehicle['fixed_count']}{unlimited}"
            )
        else:
            lines.append(
                f"**{row['display_name']}**: {row['capacity']} kg x "
                f"{source_vehicle['fixed_count']}{unlimited}"
            )

    return lines


def _is_motor_vehicle(vehicle: dict[str, Any]) -> bool:
    return "motor" in vehicle.get("name", "").lower()


def _motor_max_capacity(vehicle: dict[str, Any]) -> float | None:
    if not _is_motor_vehicle(vehicle):
        return None
    return float(vehicle.get("max_capacity", MOTOR_NON_FRAGILE_CAPACITY_KG))
