from __future__ import annotations

from dataclasses import dataclass


class PlanState:
    """Lifecycle state for plans.

    Stored/derived without breaking existing `is_published` behavior.
    """

    DRAFT = 'draft'
    REVIEW = 'review'
    PUBLISHED = 'published'
    ARCHIVED = 'archived'

    ALL = (DRAFT, REVIEW, PUBLISHED, ARCHIVED)


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    PlanState.DRAFT: {PlanState.REVIEW, PlanState.ARCHIVED},
    PlanState.REVIEW: {PlanState.DRAFT, PlanState.PUBLISHED, PlanState.ARCHIVED},
    PlanState.PUBLISHED: {PlanState.ARCHIVED, PlanState.REVIEW},
    PlanState.ARCHIVED: {PlanState.DRAFT},
}


@dataclass(frozen=True)
class PlanStateChange:
    plan_id: int
    from_state: str
    to_state: str
    reason: str | None = None
    actor_user_id: int | None = None
