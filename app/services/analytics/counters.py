"""In-memory counters for high-volume events.

We keep these in-memory to minimize DB writes for ultra-noisy traffic
(especially attack probes). Counts are flushed to the DB on-demand
(e.g., admin dashboard load) or via a scheduled job.

Note: In multi-worker deployments, each worker has its own counters.
For fully accurate global counts, back this with a shared store (Redis)
or flush counts from each worker.
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from threading import Lock


_lock = Lock()
_attack_counts: Counter[date] = Counter()
_human_counts: Counter[date] = Counter()
_bot_counts: Counter[date] = Counter()


def increment_attack(day: date) -> None:
    with _lock:
        _attack_counts[day] += 1


def increment_human(day: date) -> None:
    with _lock:
        _human_counts[day] += 1


def increment_bot(day: date) -> None:
    with _lock:
        _bot_counts[day] += 1


def snapshot_and_reset_attacks() -> dict[date, int]:
    """Return counts and reset internal counters."""

    with _lock:
        snapshot = dict(_attack_counts)
        _attack_counts.clear()
    return snapshot


def snapshot_and_reset_counts() -> tuple[dict[date, int], dict[date, int]]:
    """Return (human_counts, bot_counts) and reset internal counters."""

    with _lock:
        humans = dict(_human_counts)
        bots = dict(_bot_counts)
        _human_counts.clear()
        _bot_counts.clear()
    return humans, bots


def peek_attacks() -> dict[date, int]:
    with _lock:
        return dict(_attack_counts)


def peek_counts() -> tuple[dict[date, int], dict[date, int]]:
    with _lock:
        return dict(_human_counts), dict(_bot_counts)
