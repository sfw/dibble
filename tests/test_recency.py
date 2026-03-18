from __future__ import annotations

from datetime import datetime, timedelta, timezone

from dibble.services.recency import recency_weight


def _ref() -> datetime:
    return datetime(2026, 3, 18, 12, 0, 0, tzinfo=timezone.utc)


def test_same_time_returns_full_weight():
    ref = _ref()
    assert recency_weight(ref, ref) == 1.0


def test_within_seven_days_returns_full_weight():
    ref = _ref()
    assert recency_weight(ref - timedelta(days=3), ref) == 1.0
    assert recency_weight(ref - timedelta(days=7), ref) == 1.0


def test_at_day_fourteen_returns_0_8():
    ref = _ref()
    w = recency_weight(ref - timedelta(days=14), ref)
    assert abs(w - 0.8) < 0.01


def test_at_day_twenty_one_returns_0_5():
    ref = _ref()
    w = recency_weight(ref - timedelta(days=21), ref)
    assert abs(w - 0.5) < 0.01


def test_at_lookback_boundary_returns_0_2():
    ref = _ref()
    w = recency_weight(ref - timedelta(days=28), ref)
    assert abs(w - 0.2) < 0.01


def test_beyond_lookback_still_returns_0_2():
    ref = _ref()
    w = recency_weight(ref - timedelta(days=60), ref)
    assert w == 0.2


def test_smooth_interpolation_within_band():
    """Weights at the midpoint of a band should be strictly between the
    band endpoints, confirming smooth interpolation."""
    ref = _ref()
    # Midpoint of 7-14 band is day 10.5
    w = recency_weight(ref - timedelta(days=10, hours=12), ref)
    assert 0.8 < w < 1.0

    # Midpoint of 14-21 band is day 17.5
    w = recency_weight(ref - timedelta(days=17, hours=12), ref)
    assert 0.5 < w < 0.8

    # Midpoint of 21-28 band is day 24.5
    w = recency_weight(ref - timedelta(days=24, hours=12), ref)
    assert 0.2 < w < 0.5


def test_monotonically_decreasing():
    """Weight should never increase as event_time gets older."""
    ref = _ref()
    previous = 1.0
    for days in range(0, 35):
        w = recency_weight(ref - timedelta(days=days), ref)
        assert w <= previous + 1e-9, f"Weight increased at day {days}: {w} > {previous}"
        previous = w


def test_custom_lookback_days():
    ref = _ref()
    w = recency_weight(ref - timedelta(days=14), ref, lookback_days=14)
    assert abs(w - 0.8) < 0.01


def test_future_event_returns_full_weight():
    """An event in the 'future' (e.g. clock skew) should get full weight."""
    ref = _ref()
    w = recency_weight(ref + timedelta(hours=1), ref)
    assert w == 1.0
