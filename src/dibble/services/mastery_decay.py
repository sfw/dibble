"""Time-based mastery decay for untouched knowledge components.

When a learner has not practiced a KC for a long time, their stored mastery
should be discounted so that progression and prerequisite decisions stay
honest.  The decay is applied at read time — stored mastery values are never
mutated by decay alone.

Decay bands (smooth interpolation within each band):
  - Within 14 days  -> no decay (factor 1.0)
  - 15-28 days      -> light decay (factor -> 0.92)
  - 29-56 days      -> moderate decay (factor -> 0.78)
  - Beyond 56 days  -> heavy decay (factor -> 0.6)

The floor of 0.6 prevents mastery from vanishing entirely — a learner who
once demonstrated strong understanding retains meaningful credit, but not
enough to skip prerequisite checks after months of inactivity.
"""

from __future__ import annotations

from datetime import datetime, timezone


def mastery_decay_factor(
    last_practiced: datetime | None,
    reference_time: datetime | None = None,
) -> float:
    """Return a [0.6, 1.0] multiplicative factor reflecting how recently a KC
    was practiced.

    If *last_practiced* is ``None`` (no timestamp recorded), returns 1.0 so
    that legacy profiles without timestamps are not penalised.
    """
    if last_practiced is None:
        return 1.0
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)
    delta = reference_time - last_practiced
    days = max(0.0, delta.total_seconds() / 86_400)

    if days <= 14.0:
        return 1.0

    if days <= 28.0:
        fraction = (days - 14.0) / 14.0
        return 1.0 - fraction * (1.0 - 0.92)

    if days <= 56.0:
        fraction = (days - 28.0) / 28.0
        return 0.92 - fraction * (0.92 - 0.78)

    # Beyond 56 days: interpolate toward the floor.
    remaining = max(1.0, 90.0 - 56.0)
    fraction = min(1.0, (days - 56.0) / remaining)
    return 0.78 - fraction * (0.78 - 0.6)


def decayed_kc_mastery(
    kc_mastery: dict[str, float],
    kc_last_practiced: dict[str, datetime],
    reference_time: datetime | None = None,
) -> dict[str, float]:
    """Return a copy of *kc_mastery* with time-decay applied per KC.

    KCs without a ``kc_last_practiced`` entry are returned unchanged.
    """
    result: dict[str, float] = {}
    for kc_id, mastery in kc_mastery.items():
        factor = mastery_decay_factor(
            kc_last_practiced.get(kc_id),
            reference_time=reference_time,
        )
        result[kc_id] = round(mastery * factor, 2)
    return result
