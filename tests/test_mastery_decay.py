"""Tests for time-based mastery decay (DATA-004)."""

from datetime import datetime, timedelta, timezone

from dibble.services.mastery_decay import decayed_kc_mastery, mastery_decay_factor


def _utc(days_ago: float = 0.0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


# --- mastery_decay_factor ---


def test_no_decay_when_last_practiced_is_none():
    assert mastery_decay_factor(None) == 1.0


def test_no_decay_within_14_days():
    assert mastery_decay_factor(_utc(0)) == 1.0
    assert mastery_decay_factor(_utc(7)) == 1.0
    # At exactly 14 days there may be sub-second float drift, so use approx.
    assert abs(mastery_decay_factor(_utc(14)) - 1.0) < 0.001


def test_light_decay_between_15_and_28_days():
    factor = mastery_decay_factor(_utc(21))
    assert 0.92 < factor < 1.0  # midpoint of [1.0, 0.92]


def test_decay_at_28_days_is_0_92():
    factor = mastery_decay_factor(_utc(28))
    assert abs(factor - 0.92) < 0.01


def test_moderate_decay_between_29_and_56_days():
    factor = mastery_decay_factor(_utc(42))
    assert 0.78 < factor < 0.92  # midpoint of [0.92, 0.78]


def test_decay_at_56_days_is_0_78():
    factor = mastery_decay_factor(_utc(56))
    assert abs(factor - 0.78) < 0.01


def test_heavy_decay_beyond_56_days():
    factor = mastery_decay_factor(_utc(90))
    assert abs(factor - 0.6) < 0.01


def test_decay_floor_at_0_6():
    factor = mastery_decay_factor(_utc(365))
    assert factor >= 0.6


def test_decay_is_monotonically_decreasing():
    days = [0, 7, 14, 21, 28, 35, 42, 49, 56, 70, 90, 120]
    factors = [mastery_decay_factor(_utc(d)) for d in days]
    for i in range(len(factors) - 1):
        assert factors[i] >= factors[i + 1], (
            f"Decay factor at day {days[i]} should be >= day {days[i + 1]}"
        )


# --- decayed_kc_mastery ---


def test_decayed_kc_mastery_leaves_recent_kcs_unchanged():
    now = datetime.now(timezone.utc)
    kc_mastery = {"KC-1": 0.85, "KC-2": 0.70}
    kc_last_practiced = {
        "KC-1": now - timedelta(days=5),
        "KC-2": now - timedelta(days=10),
    }
    result = decayed_kc_mastery(kc_mastery, kc_last_practiced, reference_time=now)
    assert result["KC-1"] == 0.85
    assert result["KC-2"] == 0.70


def test_decayed_kc_mastery_reduces_stale_kc():
    now = datetime.now(timezone.utc)
    kc_mastery = {"KC-1": 0.90, "KC-2": 0.90}
    kc_last_practiced = {
        "KC-1": now - timedelta(days=5),  # recent
        "KC-2": now - timedelta(days=60),  # stale
    }
    result = decayed_kc_mastery(kc_mastery, kc_last_practiced, reference_time=now)
    assert result["KC-1"] == 0.90  # no decay
    assert result["KC-2"] < 0.90  # decayed
    assert result["KC-2"] >= 0.54  # 0.90 * 0.6 floor


def test_decayed_kc_mastery_no_timestamp_means_no_decay():
    now = datetime.now(timezone.utc)
    kc_mastery = {"KC-1": 0.80}
    kc_last_practiced: dict[str, datetime] = {}  # no timestamp
    result = decayed_kc_mastery(kc_mastery, kc_last_practiced, reference_time=now)
    assert result["KC-1"] == 0.80


def test_decayed_kc_mastery_applies_graduated_decay():
    now = datetime.now(timezone.utc)
    kc_mastery = {"KC-A": 0.80, "KC-B": 0.80, "KC-C": 0.80}
    kc_last_practiced = {
        "KC-A": now - timedelta(days=21),  # light decay
        "KC-B": now - timedelta(days=42),  # moderate decay
        "KC-C": now - timedelta(days=90),  # heavy decay
    }
    result = decayed_kc_mastery(kc_mastery, kc_last_practiced, reference_time=now)
    assert result["KC-A"] > result["KC-B"] > result["KC-C"]
    assert result["KC-A"] > 0.70  # 0.80 * ~0.96
    assert result["KC-C"] >= 0.48  # 0.80 * 0.6
