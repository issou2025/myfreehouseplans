from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class PolicyIssue:
    code: str
    message: str


@dataclass
class PlanDiagnostics:
    errors: List[PolicyIssue] = field(default_factory=list)
    warnings: List[PolicyIssue] = field(default_factory=list)
    suggestions: List[PolicyIssue] = field(default_factory=list)

    @property
    def ok_to_publish(self) -> bool:
        return len(self.errors) == 0


def _normalize_price(value: Any) -> Optional[float]:
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_allowed_gumroad_url(raw_url: Optional[str]) -> bool:
    """Pure validation for Gumroad redirect safety.

    Mirrors the route-layer allowlist logic without importing Flask.
    """

    if not raw_url:
        return False

    try:
        parsed = urlparse(raw_url)
    except Exception:
        return False

    if parsed.scheme not in ('http', 'https'):
        return False

    host = (parsed.hostname or '').lower()
    if not host:
        return False

    return host == 'gumroad.com' or host.endswith('.gumroad.com') or host == 'gum.co'


def diagnose_plan(plan: Any) -> PlanDiagnostics:
    """Compute a best-effort, explainable policy view for a plan.

    This is intentionally framework-agnostic: `plan` can be an ORM model
    instance or a lightweight object with matching attributes.

    Additive policy: emits errors/warnings/suggestions but does not mutate.
    """

    diag = PlanDiagnostics()

    title = (getattr(plan, 'title', None) or '').strip()
    description = (getattr(plan, 'description', None) or '').strip()
    short_description = (getattr(plan, 'short_description', None) or '').strip()

    if not title:
        diag.errors.append(PolicyIssue('plan.title.missing', 'Title is required.'))

    if not description:
        diag.errors.append(PolicyIssue('plan.description.missing', 'Description is required.'))

    if not short_description:
        diag.suggestions.append(PolicyIssue('plan.short_description.missing', 'Add an architectural summary (1–2 sentences) to improve cards and SEO.'))

    # Categories: optional duck-typing support for ORM relationship.
    categories = getattr(plan, 'categories', None)
    try:
        has_categories = bool(categories) and len(list(categories)) > 0
    except Exception:
        has_categories = bool(categories)

    if not has_categories:
        diag.errors.append(PolicyIssue('plan.categories.missing', 'Select at least one category.'))

    # Core media
    cover_image = getattr(plan, 'cover_image', None)
    if not cover_image:
        diag.suggestions.append(PolicyIssue('plan.cover_image.missing', 'Add a cover image to improve listing quality and conversion.'))

    # Pack availability SSOT
    free_pdf_file = getattr(plan, 'free_pdf_file', None)
    gumroad_pack_2_url = (getattr(plan, 'gumroad_pack_2_url', None) or '').strip()
    gumroad_pack_3_url = (getattr(plan, 'gumroad_pack_3_url', None) or '').strip()

    price_pack_1 = _normalize_price(getattr(plan, 'price_pack_1', None))
    price_pack_2 = _normalize_price(getattr(plan, 'price_pack_2', None))
    price_pack_3 = _normalize_price(getattr(plan, 'price_pack_3', None))

    if price_pack_1 is not None and price_pack_1 < 0:
        diag.errors.append(PolicyIssue('pack1.price.negative', 'Pack 1 value cannot be negative.'))

    if price_pack_2 is not None and price_pack_2 < 0:
        diag.errors.append(PolicyIssue('pack2.price.negative', 'Pack 2 price cannot be negative.'))

    if price_pack_3 is not None and price_pack_3 < 0:
        diag.errors.append(PolicyIssue('pack3.price.negative', 'Pack 3 price cannot be negative.'))

    pack1_available = bool(free_pdf_file)
    if not pack1_available:
        diag.warnings.append(PolicyIssue('pack1.file.missing', 'Free pack is not downloadable until a Free PDF is uploaded.'))

    if gumroad_pack_2_url:
        if not is_allowed_gumroad_url(gumroad_pack_2_url):
            diag.errors.append(PolicyIssue('pack2.gumroad.invalid', 'Pack 2 Gumroad URL is not an allowed Gumroad domain.'))
        if price_pack_2 is None:
            diag.suggestions.append(PolicyIssue('pack2.price.missing', 'Consider setting Pack 2 price to keep pricing consistent.'))
    else:
        # Only a suggestion (pack 2 is optional)
        diag.suggestions.append(PolicyIssue('pack2.gumroad.missing', 'Add a Gumroad link if you want to sell Pack 2.'))

    if gumroad_pack_3_url:
        if not is_allowed_gumroad_url(gumroad_pack_3_url):
            diag.errors.append(PolicyIssue('pack3.gumroad.invalid', 'Pack 3 Gumroad URL is not an allowed Gumroad domain.'))
        if price_pack_3 is None:
            diag.suggestions.append(PolicyIssue('pack3.price.missing', 'Consider setting Pack 3 price to keep pricing consistent.'))

        # File-safety rule (best-effort): we cannot verify Gumroad contents, so we warn.
        diag.warnings.append(
            PolicyIssue(
                'pack3.contents.unverifiable',
                'Pack 3 should include DWG/RVT/IFC deliverables; this cannot be verified automatically for Gumroad links. Confirm contents before publishing.',
            )
        )
    else:
        diag.suggestions.append(PolicyIssue('pack3.gumroad.missing', 'Add a Gumroad link if you want to sell Pack 3.'))

    # Pricing coherence
    display_price = _normalize_price(getattr(plan, 'price', None))
    sale_price = _normalize_price(getattr(plan, 'sale_price', None))

    if display_price is None:
        diag.errors.append(PolicyIssue('pricing.display.missing', 'Display price is required.'))

    if sale_price is not None and display_price is not None and sale_price >= display_price:
        diag.warnings.append(PolicyIssue('pricing.sale.not_lower', 'Sale price should be lower than the display price.'))

    # Publication readiness
    is_published = bool(getattr(plan, 'is_published', False))
    if is_published and not diag.ok_to_publish:
        diag.warnings.append(
            PolicyIssue(
                'publish.blockers.present',
                'This plan is marked Published but has policy errors; consider switching to Draft until resolved.',
            )
        )

    return diag


def diagnostics_to_flash_messages(diag: PlanDiagnostics) -> List[tuple[str, str]]:
    """Convert diagnostics into (category, message) pairs suitable for Flask flash()."""

    messages: List[tuple[str, str]] = []

    for issue in diag.errors:
        messages.append(('danger', issue.message))

    for issue in diag.warnings:
        messages.append(('warning', issue.message))

    for issue in diag.suggestions:
        messages.append(('info', issue.message))

    return messages
