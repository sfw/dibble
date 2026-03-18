"""Unified recency weighting utility for observation and profile signals.

Policy bands (with smooth interpolation within each band):
  - Within 7 days  -> 1.0
  - 8-14 days      -> 0.8
  - 15-21 days     -> 0.5
  - Beyond 21 days -> 0.2

Events older than ``lookback_days`` still receive 0.2 rather than 0.0
because even stale evidence carries *some* diagnostic value.
"""

from __future__ import annotations

from datetime import datetime


def recency_weight(
    event_time: datetime,
    reference_time: datetime,
    lookback_days: int = 28,
) -> float:
    """Return a [0.2, 1.0] weight reflecting how recent *event_time* is
    relative to *reference_time*.

    Smooth linear interpolation is applied within each recency band so
    that the weight transitions gradually rather than jumping at band
    boundaries.
    """
    delta = reference_time - event_time
    days = max(0.0, delta.total_seconds() / 86_400)

    if days > lookback_days:
        return 0.2

    # Band edges and corresponding weight targets
    #   [0, 7]   -> 1.0
    #   (7, 14]  -> 0.8
    #   (14, 21] -> 0.5
    #   (21, ..]  -> 0.2
    if days <= 7.0:
        # Fully recent -- no discount.  We still interpolate gently toward
        # the next band edge so the transition at day 7 is seamless.
        # At day 0 weight = 1.0, at day 7 weight = 1.0 (top of next band).
        return 1.0

    if days <= 14.0:
        # Interpolate from 1.0 (day 7) to 0.8 (day 14).
        fraction = (days - 7.0) / 7.0
        return 1.0 - fraction * (1.0 - 0.8)

    if days <= 21.0:
        # Interpolate from 0.8 (day 14) to 0.5 (day 21).
        fraction = (days - 14.0) / 7.0
        return 0.8 - fraction * (0.8 - 0.5)

    # Interpolate from 0.5 (day 21) toward 0.2 (lookback_days).
    remaining = max(1.0, lookback_days - 21.0)
    fraction = min(1.0, (days - 21.0) / remaining)
    return 0.5 - fraction * (0.5 - 0.2)
