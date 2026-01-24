"""Dashboard queries for smart analytics."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models import DailyTrafficStat, RecentLog, Order
from app.services.analytics.counters import peek_attacks, peek_counts


def _daterange(start: date, days: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(days)]


def build_dashboard_payload(*, days: int = 7) -> dict:
    today = datetime.utcnow().date()
    start = today - timedelta(days=days - 1)

    day_list = _daterange(start, days)

    # Pull aggregated stats.
    daily_rows = (
        DailyTrafficStat.query
        .filter(DailyTrafficStat.date >= start)
        .filter(DailyTrafficStat.date <= today)
        .all()
    )
    daily_by_date = {row.date: row for row in daily_rows}

    # Pull recent logs aggregation for the window (covers "today" and un-flushed days).
    date_expr = func.date(RecentLog.timestamp)
    recent_counts_rows = (
        db.session.query(date_expr.label('d'), RecentLog.traffic_type, func.count(RecentLog.id))
        .filter(RecentLog.timestamp >= datetime.combine(start, datetime.min.time()))
        .group_by('d', RecentLog.traffic_type)
        .all()
    )

    recent_by_day: dict[date, dict[str, int]] = {}
    for dval, ttype, count in recent_counts_rows:
        if dval is None:
            continue
        if isinstance(dval, str):
            try:
                d_obj = datetime.strptime(dval, '%Y-%m-%d').date()
            except Exception:
                continue
        else:
            d_obj = dval
        recent_by_day.setdefault(d_obj, {})[ttype] = int(count or 0)

    # In-memory counters (best-effort; per-worker).
    attacks_mem = peek_attacks()
    humans_mem, bots_mem = peek_counts()

    # Revenue for last N days.
    revenue_rows = (
        db.session.query(func.date(Order.created_at).label('d'), func.coalesce(func.sum(Order.amount), 0))
        .filter(Order.status == 'completed')
        .filter(Order.created_at >= datetime.combine(start, datetime.min.time()))
        .group_by('d')
        .all()
    )
    revenue_by_day: dict[date, float] = {}
    for dval, amount in revenue_rows:
        if dval is None:
            continue
        if isinstance(dval, str):
            try:
                d_obj = datetime.strptime(dval, '%Y-%m-%d').date()
            except Exception:
                continue
        else:
            d_obj = dval
        try:
            revenue_by_day[d_obj] = float(amount or 0)
        except Exception:
            revenue_by_day[d_obj] = 0.0

    series = []
    totals = {'human': 0, 'bot': 0, 'attack': 0, 'revenue': 0.0}

    for day in day_list:
        base = daily_by_date.get(day)
        human = int(getattr(base, 'human_visits', 0) or 0)
        bot = int(getattr(base, 'bot_visits', 0) or 0)
        attack = int(getattr(base, 'blocked_attacks', 0) or 0)

        # Add live/unflushed signals.
        rc = recent_by_day.get(day, {})
        human += int(rc.get('human', 0))
        bot += int(rc.get('bot', 0))
        attack += int(rc.get('attack', 0))

        human += int(humans_mem.get(day, 0) or 0)
        bot += int(bots_mem.get(day, 0) or 0)
        attack += int(attacks_mem.get(day, 0) or 0)

        revenue = float(revenue_by_day.get(day, 0.0) or 0.0)

        totals['human'] += human
        totals['bot'] += bot
        totals['attack'] += attack
        totals['revenue'] += revenue

        series.append({
            'date': day.isoformat(),
            'label': day.strftime('%a'),
            'human': human,
            'bot': bot,
            'attack': attack,
            'revenue': revenue,
        })

    # Top countries (humans, last N days).
    top_countries_rows = (
        db.session.query(RecentLog.country_code, RecentLog.country_name, func.count(RecentLog.id))
        .filter(RecentLog.timestamp >= datetime.combine(start, datetime.min.time()))
        .filter(RecentLog.traffic_type == 'human')
        .group_by(RecentLog.country_code, RecentLog.country_name)
        .order_by(func.count(RecentLog.id).desc())
        .limit(10)
        .all()
    )

    top_countries = []
    for code, name, count in top_countries_rows:
        top_countries.append({
            'code': (code or '').upper(),
            'name': name or 'Unknown',
            'count': int(count or 0),
        })

    # Conversion rate: completed orders / human visits (window).
    sales_count = (
        Order.query
        .filter(Order.status == 'completed')
        .filter(Order.created_at >= datetime.combine(start, datetime.min.time()))
        .count()
    )
    human_total = max(1, int(totals['human']))
    conversion_rate = float(sales_count) / float(human_total)

    return {
        'window_days': days,
        'series': series,
        'totals': {
            'human': int(totals['human']),
            'bot': int(totals['bot']),
            'attack': int(totals['attack']),
            'revenue': float(totals['revenue']),
            'sales': int(sales_count),
            'conversion_rate': conversion_rate,
        },
        'top_countries': top_countries,
    }
