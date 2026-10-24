"""Temporal filtering and cutoff enforcement at audit_at timestamp.
"""

from typing import Any, Dict, List, Optional
import pandas as pd


class TemporalFilter:
    """Enforces evidence admissibility and historical state reconstruction at audit_at."""

    @staticmethod
    def parse_timestamp(ts: Any) -> Optional[pd.Timestamp]:
        if pd.isna(ts) or not ts:
            return None
        try:
            return pd.to_datetime(ts)
        except Exception:
            return None

    @staticmethod
    def is_admissible(captured_at: Any, audit_at: Any) -> bool:
        """Admissible if and only if captured_at <= audit_at."""
        c_dt = TemporalFilter.parse_timestamp(captured_at)
        a_dt = TemporalFilter.parse_timestamp(audit_at)
        if c_dt is None or a_dt is None:
            return False
        return c_dt <= a_dt

    @staticmethod
    def filter_activity(activity_df: pd.DataFrame, cutoff: Any) -> pd.DataFrame:
        """Filter system activity events that occurred at or before cutoff."""
        c_dt = TemporalFilter.parse_timestamp(cutoff)
        if c_dt is None:
            return activity_df
        if "event_dt" in activity_df.columns:
            return activity_df[activity_df["event_dt"] <= c_dt]
        return activity_df[pd.to_datetime(activity_df["event_time"]) <= c_dt]
