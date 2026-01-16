from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Iterable, Optional

from sqlalchemy import asc, desc, or_
from sqlalchemy.orm import load_only

from app.models import ContactMessage


IMPORTANT_TAG = "[IMPORTANT]"


@dataclass(frozen=True)
class InboxFilters:
    status: str = 'open'
    inquiry_type: str = ''

    q: str = ''
    sender: str = ''
    subject: str = ''

    date_from: str = ''  # YYYY-MM-DD
    date_to: str = ''    # YYYY-MM-DD

    important: str = ''  # '', '1'
    include_body: str = ''  # '', '1'

    sort: str = 'date_desc'
    per_page: int = 20


def _parse_ymd(value: str) -> Optional[date]:
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except Exception:
        return None


def _day_start(d: date) -> datetime:
    return datetime.combine(d, time.min)


def _day_end(d: date) -> datetime:
    return datetime.combine(d, time.max)


def is_important_message(message: ContactMessage) -> bool:
    notes = (message.admin_notes or '').upper()
    if IMPORTANT_TAG in notes:
        return True

    # Heuristic fallback (no extra DB fields): prioritize high-signal keywords.
    text = f"{message.subject or ''} {message.inquiry_type or ''} {message.reference_code or ''}".lower()
    keywords = (
        'urgent', 'asap', 'refund', 'payment', 'error', 'bug', 'problem', 'download', 'not working', 'failed'
    )
    if any(k in text for k in keywords):
        return True
    if message.has_attachment:
        return True
    if message.reference_code:
        return True
    return False


def toggle_important(notes: str | None, make_important: bool) -> str:
    raw = (notes or '').strip()
    lines = raw.splitlines() if raw else []
    has_tag = bool(lines and lines[0].strip().upper().startswith(IMPORTANT_TAG))

    if make_important:
        if has_tag:
            return raw
        if not raw:
            return IMPORTANT_TAG
        return IMPORTANT_TAG + "\n" + raw

    # remove important
    if not raw:
        return ''
    if has_tag:
        remaining = "\n".join(lines[1:]).strip()
        return remaining
    # also remove any stray tag occurrences
    cleaned = raw.replace(IMPORTANT_TAG, '').strip()
    return cleaned


def build_messages_query(filters: InboxFilters):
    """Build a performant base query for the inbox list.

    Key performance notes:
    - Avoid loading large TEXT columns (message/admin_notes/email_error) in list views.
    - Keep filters in SQL and paginate.
    """

    query = ContactMessage.query

    query = query.options(
        load_only(
            ContactMessage.id,
            ContactMessage.name,
            ContactMessage.email,
            ContactMessage.phone,
            ContactMessage.subject,
            ContactMessage.inquiry_type,
            ContactMessage.reference_code,
            ContactMessage.plan_snapshot,
            ContactMessage.attachment_path,
            ContactMessage.attachment_name,
            ContactMessage.subscribe,
            ContactMessage.status,
            ContactMessage.created_at,
            ContactMessage.email_status,
            ContactMessage.responded_at,
            ContactMessage.status_updated_at,
            ContactMessage.admin_notes,
        )
    )

    # Status filter
    if filters.status == 'open':
        query = query.filter(ContactMessage.status.in_((ContactMessage.STATUS_NEW, ContactMessage.STATUS_IN_PROGRESS)))
    elif filters.status and filters.status != 'all':
        query = query.filter(ContactMessage.status == filters.status)

    # Inquiry filter
    if filters.inquiry_type:
        query = query.filter(ContactMessage.inquiry_type == filters.inquiry_type)

    # Date range
    df = _parse_ymd(filters.date_from) if filters.date_from else None
    dt = _parse_ymd(filters.date_to) if filters.date_to else None
    if df and dt and df > dt:
        df, dt = dt, df
    if df:
        query = query.filter(ContactMessage.created_at >= _day_start(df))
    if dt:
        query = query.filter(ContactMessage.created_at <= _day_end(dt))

    # Targeted search
    if filters.sender:
        like = f"%{filters.sender}%"
        query = query.filter(or_(ContactMessage.email.ilike(like), ContactMessage.name.ilike(like)))

    if filters.subject:
        like = f"%{filters.subject}%"
        query = query.filter(ContactMessage.subject.ilike(like))

    # Keyword search (optionally includes body)
    if filters.q:
        like = f"%{filters.q}%"
        clauses = [
            ContactMessage.subject.ilike(like),
            ContactMessage.email.ilike(like),
            ContactMessage.name.ilike(like),
            ContactMessage.reference_code.ilike(like),
        ]
        if filters.include_body == '1':
            clauses.append(ContactMessage.message.ilike(like))
        query = query.filter(or_(*clauses))

    # Important filter (stored in admin_notes via tag)
    if filters.important == '1':
        query = query.filter(ContactMessage.admin_notes.ilike(f"{IMPORTANT_TAG}%"))

    # Sorting
    sort = filters.sort or 'date_desc'
    if sort == 'date_asc':
        query = query.order_by(asc(ContactMessage.created_at))
    elif sort == 'status':
        query = query.order_by(asc(ContactMessage.status), desc(ContactMessage.created_at))
    elif sort == 'sender':
        query = query.order_by(asc(ContactMessage.email), desc(ContactMessage.created_at))
    elif sort == 'subject':
        query = query.order_by(asc(ContactMessage.subject), desc(ContactMessage.created_at))
    else:
        query = query.order_by(desc(ContactMessage.created_at))

    return query


def message_preview_text(message_text: str | None, limit: int = 280) -> str:
    raw = (message_text or '').strip()
    if not raw:
        return ''
    if len(raw) <= limit:
        return raw
    return raw[:limit].rstrip() + '…'
