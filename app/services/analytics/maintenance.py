"""Analytics maintenance: aggregation + retention.

- Aggregate `RecentLog` into `DailyTrafficStat`.
- Merge in attack counts from in-memory counters.
- Delete `RecentLog` entries older than retention window.

Designed to be safe to run frequently.
"""

from __future__ import annotations

from datetime import datetime, timedelta, date

from sqlalchemy import func

from app.extensions import db
from app.models import DailyTrafficStat, RecentLog, Order
from app.services.analytics.counters import snapshot_and_reset_attacks, snapshot_and_reset_counts


RECENT_LOG_RETENTION_DAYS = 7


def _utc_today() -> date:
    return datetime.utcnow().date()


def clean_old_logs(*, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=RECENT_LOG_RETENTION_DAYS)

    # 1) Flush in-memory counters into DailyTrafficStat.
    flushed_attacks = 0
    flushed_humans = 0
    flushed_bots = 0

    humans_snapshot, bots_snapshot = snapshot_and_reset_counts()
    for day, count in humans_snapshot.items():
        if not count:
            continue
        row = db.session.get(DailyTrafficStat, day)
        if row is None:
            row = DailyTrafficStat(date=day, human_visits=0, bot_visits=0, blocked_attacks=0, revenue=0.0)
            db.session.add(row)
        row.human_visits = int(row.human_visits or 0) + int(count)
        flushed_humans += int(count)

    for day, count in bots_snapshot.items():
        if not count:
            continue
        row = db.session.get(DailyTrafficStat, day)
        if row is None:
            row = DailyTrafficStat(date=day, human_visits=0, bot_visits=0, blocked_attacks=0, revenue=0.0)
            db.session.add(row)
        row.bot_visits = int(row.bot_visits or 0) + int(count)
        flushed_bots += int(count)

    attack_snapshot = snapshot_and_reset_attacks()
    for day, count in attack_snapshot.items():
        if not count:
            continue
        row = db.session.get(DailyTrafficStat, day)
        if row is None:
            row = DailyTrafficStat(date=day, human_visits=0, bot_visits=0, blocked_attacks=0, revenue=0.0)
            db.session.add(row)
        row.blocked_attacks = int(row.blocked_attacks or 0) + int(count)
        flushed_attacks += int(count)

    # 2) Aggregate older RecentLog rows (<= cutoff) into daily stats.
    #    We aggregate logs older than retention window since those are about to be deleted.
    aggregated_days = 0
    aggregated_rows = 0

    date_expr = func.date(RecentLog.timestamp)

    rows = (
        db.session.query(date_expr.label('d'), RecentLog.traffic_type, func.count(RecentLog.id))
        .filter(RecentLog.timestamp < cutoff)
        .group_by('d', RecentLog.traffic_type)
        .all()
    )

    # Map date -> {type -> count}
    by_day: dict[date, dict[str, int]] = {}
    for day_value, traffic_type, count in rows:
        if day_value is None:
            continue
        # SQL dialects may return string for func.date on SQLite.
        if isinstance(day_value, str):
            try:
                day_obj = datetime.strptime(day_value, '%Y-%m-%d').date()
            except Exception:
                continue
        else:
            day_obj = day_value
        by_day.setdefault(day_obj, {})[traffic_type] = int(count or 0)
        aggregated_rows += int(count or 0)

    for day, counts in by_day.items():
        stat = db.session.get(DailyTrafficStat, day)
        if stat is None:
            stat = DailyTrafficStat(date=day)
            db.session.add(stat)

        stat.human_visits = int(stat.human_visits or 0) + int(counts.get('human', 0))
        stat.bot_visits = int(stat.bot_visits or 0) + int(counts.get('bot', 0))
        stat.blocked_attacks = int(stat.blocked_attacks or 0) + int(counts.get('attack', 0))
        aggregated_days += 1

        # Store top countries for that day (humans only) as a small list.
        country_rows = (
            db.session.query(RecentLog.country_code, RecentLog.country_name, func.count(RecentLog.id))
            .filter(RecentLog.timestamp < cutoff)
            .filter(date_expr == day)
            .filter(RecentLog.traffic_type == 'human')
            .group_by(RecentLog.country_code, RecentLog.country_name)
            .order_by(func.count(RecentLog.id).desc())
            .limit(8)
            .all()
        )
        top = []
        for code, name, c in country_rows:
            top.append({'code': code or '', 'name': name or 'Unknown', 'count': int(c or 0)})
        stat.top_countries = top

        # Revenue for that day (completed orders)
        revenue_row = (
            db.session.query(func.coalesce(func.sum(Order.amount), 0))
            .filter(func.date(Order.created_at) == day)
            .filter(Order.status == 'completed')
            .scalar()
        )
        try:
            stat.revenue = float(revenue_row or 0)
        except Exception:
            stat.revenue = float(stat.revenue or 0)

    # 3) Delete old recent logs.
    deleted = (
        RecentLog.query
        .filter(RecentLog.timestamp < cutoff)
        .delete(synchronize_session=False)
    )

    db.session.commit()

    return {
        'flushed_attacks': flushed_attacks,
        'flushed_humans': flushed_humans,
        'flushed_bots': flushed_bots,
        'aggregated_days': aggregated_days,
        'aggregated_rows': aggregated_rows,
        'deleted_recent_logs': int(deleted or 0),
    }
