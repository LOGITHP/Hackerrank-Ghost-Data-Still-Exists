"""Unit tests for TemporalFilter logic and cutoff boundaries.
"""

import pandas as pd
from code.engine.temporal_filter import TemporalFilter


def test_parse_timestamp():
    ts = TemporalFilter.parse_timestamp("2026-09-15T12:00:00Z")
    assert ts is not None
    assert ts.year == 2026
    assert ts.month == 9
    assert ts.day == 15

    assert TemporalFilter.parse_timestamp(None) is None
    assert TemporalFilter.parse_timestamp("") is None


def test_is_admissible():
    # Evidence captured before audit_at is admissible
    assert TemporalFilter.is_admissible("2026-09-02T23:00:00Z", "2026-09-03T11:30:00Z") is True
    # Evidence captured exactly at audit_at is admissible
    assert TemporalFilter.is_admissible("2026-09-15T12:00:00Z", "2026-09-15T12:00:00Z") is True
    # Evidence captured AFTER audit_at is INADMISSIBLE
    assert TemporalFilter.is_admissible("2026-09-17T12:00:00Z", "2026-09-15T12:00:00Z") is False


def test_filter_activity():
    df = pd.DataFrame([
        {"activity_id": "a1", "event_time": "2026-09-01T10:00:00Z"},
        {"activity_id": "a2", "event_time": "2026-09-05T10:00:00Z"},
        {"activity_id": "a3", "event_time": "2026-09-10T10:00:00Z"},
    ])
    df["event_dt"] = pd.to_datetime(df["event_time"])

    filtered = TemporalFilter.filter_activity(df, "2026-09-05T12:00:00Z")
    assert len(filtered) == 2
    assert "a3" not in filtered["activity_id"].values
