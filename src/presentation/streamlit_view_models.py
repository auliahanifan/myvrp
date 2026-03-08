from __future__ import annotations

from typing import Any

import pandas as pd


def preview_dataframe(preview_rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not preview_rows:
        return pd.DataFrame()
    return pd.DataFrame(preview_rows)


def records_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)
