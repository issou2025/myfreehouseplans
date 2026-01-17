"""
Main Blueprint - Public Routes

This blueprint handles all public-facing routes including:
- Homepage
- House plans listing and detail pages
- About, Contact, Privacy, Terms pages
- Sitemap
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, Response, jsonify
from flask import send_file, abort
from datetime import datetime
from app.models import HousePlan, Category, Order, ContactMessage
from app.forms import ContactForm, SearchForm
from app.extensions import db, mail
from app.seo import generate_meta_tags, generate_product_schema, generate_breadcrumb_schema, generate_sitemap
from flask_mail import Message as MailMessage
from sqlalchemy import or_, func, cast
from sqlalchemy.orm import selectinload
from sqlalchemy.types import Float
import os
import mimetypes
from urllib.parse import urlparse
from app.utils.uploads import save_uploaded_file, resolve_protected_upload
from app.utils.media import is_absolute_url, upload_url
from app.utils.pack_visibility import load_pack_visibility, filter_pack_tiers
from app.utils.visitor_tracking import tag_visit_identity
from werkzeug.exceptions import HTTPException
import traceback
from sqlalchemy.exc import SQLAlchemyError

# Create Blueprint
main_bp = Blueprint('main', __name__)


NARRATIVE_FILTERS = {
    'active_family': {
        'label': 'For an active family',
        'summary': 'Flexible layouts, gear storage, and at least three bedrooms.',
        'helper': 'Enough room for homework, bikes, and weekend sleepovers.',
    },
    'rental_ready': {
        'label': 'Ideal for rental investment',
        'summary': 'Efficient footprints with easy-to-maintain finishes.',
        'helper': 'Balanced bedroom mixes and simple circulation.',
    },
    'hot_climate': {
        'label': 'Comfortable in hot climates',
        'summary': 'Passive cooling cues and shaded outdoor areas.',
        'helper': 'Look for verandas, cross-ventilation, and roof overhangs.',
    },
    'compact_affordable': {
        'label': 'Compact and affordable',
        'summary': 'Under 1,400 sq ft with modest pricing.',
        'helper': 'Light on materials, big on usability.',
    },
}


GUIDE_ARTICLES = {
    'choose-family-plan': {
        'title': 'How to pick a balanced family plan',
        'description': 'A simple way to compare area, living zones, and budget before committing.',
        'sections': [
            'Start with daily life: how many activities truly happen at home, and which rooms need to stay quiet?',
            'Prioritize transitional spaces (mudroom, bright laundry) to absorb family rhythm.',
            'Seek plans with at least one main-level bedroom: great for guests or remote work.',
        ],
        'cta': 'See all family plans',
        'cta_url': '/plans?type=family',
    },
    'budget-vs-surface': {
        'title': 'Budget versus area: finding the balance',
        'description': 'Our architects explain how to reason in cost per square meter and avoid surprises.',
        'sections': [
            'Set an overall budget then remove 10% for contingencies. The remainder is for plans + construction.',
            'Compare plans using cost per square meter/foot: it reveals where complexity hides.',
            'Invest in the envelope (structure, insulation) before finishes. That preserves long-term value.',
        ],
        'cta': 'Plans tuned for budget and area',
        'cta_url': '/plans?sort=price_low',
    },
    'build-hot-climate': {
        'title': 'Building in hot climates',
        'description': 'Orientation, cross-ventilation, and the right materials: the winning trio.',
        'sections': [
            'Favor ventilated roofs and higher ceilings to buffer heat.',
            'Add generous roof overhangs and breezeways for cross-ventilation.',
            'Choose light materials and movable solar shading to stay flexible.',
        ],
        'cta': 'Plans designed for tropical climates',
        'cta_url': '/plans?narrative=hot_climate',
    },
}


def _get_arg(args, key, cast=None):
    """Safely fetch query parameters from MultiDict or plain dict."""
    if isinstance(args, dict):
        value = args.get(key)
    else:
        value = args.get(key)

    if value is None:
        return None

    if isinstance(value, str):
        stripped = value.strip()
        if stripped == '':
            return None
        value = stripped

    if cast is not None:
        try:
            return cast(value)
        except (TypeError, ValueError):
            return None
    return value


def _build_catalog_query(args):
    """Centralized builder for catalog queries (listing, fragments, API)."""

    query = HousePlan.query.filter_by(is_published=True)
    order_clauses = []

    search = _get_arg(args, 'q')
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                HousePlan.reference_code.ilike(like),
                HousePlan.title.ilike(like),
                HousePlan.description.ilike(like),
            )
        )

        numeric = None
        try:
            numeric = float(search.replace(',', ''))
        except Exception:
            numeric = None
        if numeric is not None:
            area_expr = func.coalesce(HousePlan.total_area_sqft, cast(HousePlan.square_feet, Float), 0.0)
            order_clauses.append(func.abs(area_expr - numeric).asc())

    category_slug = _get_arg(args, 'category')
    if category_slug:
        category = Category.query.filter_by(slug=category_slug).first_or_404()
        query = query.join(HousePlan.categories).filter(Category.id == category.id)

    plan_type = _get_arg(args, 'type')
    if plan_type:
        query = query.filter(HousePlan.plan_type == plan_type)

    min_bedrooms = _get_arg(args, 'bedrooms', int)
    if min_bedrooms:
        beds_expr = func.coalesce(HousePlan.number_of_bedrooms, HousePlan.bedrooms, 0)
        query = query.filter(beds_expr >= min_bedrooms)

    min_bathrooms = _get_arg(args, 'bathrooms', int)
    if min_bathrooms:
        baths_expr = func.coalesce(HousePlan.number_of_bathrooms, HousePlan.bathrooms, 0)
        query = query.filter(baths_expr >= min_bathrooms)

    area_min = _get_arg(args, 'area_min', float)
    area_max = _get_arg(args, 'area_max', float)
    if area_min is not None or area_max is not None:
        area_expr = func.coalesce(HousePlan.total_area_sqft, cast(HousePlan.square_feet, Float), 0.0)
        if area_min is not None:
            query = query.filter(area_expr >= area_min)
        if area_max is not None:
            query = query.filter(area_expr <= area_max)

    budget_min = _get_arg(args, 'budget_min', float)
    budget_max = _get_arg(args, 'budget_max', float)
    if budget_min is not None or budget_max is not None:
        price_expr = func.coalesce(HousePlan.sale_price, HousePlan.price)
        if budget_min is not None:
            query = query.filter(price_expr >= budget_min)
        if budget_max is not None:
            query = query.filter(price_expr <= budget_max)

    sort = _get_arg(args, 'sort') or 'newest'
    if sort == 'price_low':
        order_clauses.append(HousePlan.price.asc())
    elif sort == 'price_high':
        order_clauses.append(HousePlan.price.desc())
    elif sort == 'popular':
        order_clauses.append(HousePlan.views_count.desc())
    else:
        order_clauses.append(HousePlan.created_at.desc())

    narrative = _get_arg(args, 'narrative')
    if narrative:
        query = _apply_narrative_filter(query, narrative)

    if not order_clauses:
        order_clauses.append(HousePlan.created_at.desc())

    query = query.order_by(*order_clauses)

    return query


def _apply_narrative_filter(query, narrative_key):
    """Translate lifestyle narratives into SQL-friendly filters."""

    key = (narrative_key or '').strip()
    beds_expr = func.coalesce(HousePlan.number_of_bedrooms, HousePlan.bedrooms, 0)
    baths_expr = func.coalesce(HousePlan.number_of_bathrooms, HousePlan.bathrooms, 0)
    area_expr = func.coalesce(HousePlan.total_area_sqft, cast(HousePlan.square_feet, Float), 0.0)
    price_expr = func.coalesce(HousePlan.sale_price, HousePlan.price)

    if key == 'active_family':
        query = query.filter(beds_expr >= 3)
        query = query.filter(area_expr >= 1400)
        query = query.filter(or_(HousePlan.plan_type == 'family', HousePlan.ideal_for.ilike('%family%')))
    elif key == 'rental_ready':
        query = query.filter(or_(HousePlan.plan_type == 'rental', HousePlan.ideal_for.ilike('%rental%')))
        query = query.filter(baths_expr >= 2)
    elif key == 'hot_climate':
        query = query.filter(or_(HousePlan.suitable_climate.ilike('%hot%'), HousePlan.suitable_climate.ilike('%tropical%')))
    elif key == 'compact_affordable':
        query = query.filter(area_expr <= 1400)
        query = query.filter(price_expr <= 120000)
    return query


def _get_popular_plans(limit=6):
    try:
        return (
            HousePlan.query
            .filter_by(is_published=True)
            .order_by(HousePlan.views_count.desc(), HousePlan.created_at.desc())
            .limit(limit)
            .all()
        )
    except Exception:
        return []


def _get_new_arrivals(limit=6):
    try:
        return (
            HousePlan.query
            .filter_by(is_published=True)
            .order_by(HousePlan.created_at.desc())
            .limit(limit)
            .all()
        )
    except Exception:
        return []


def _get_climate_focus(limit=6):
    try:
        base = (
            HousePlan.query
            .filter(HousePlan.is_published.is_(True))
            .filter(or_(HousePlan.suitable_climate.ilike('%tropical%'), HousePlan.suitable_climate.ilike('%hot%')))
            .order_by(HousePlan.created_at.desc())
        )
        plans = base.limit(limit).all()
        if plans:
            return plans
        return _get_new_arrivals(limit)
    except Exception:
        return []


def _find_similar_plans(plan: HousePlan, limit: int = 6):
    """Return plans similar to the provided plan based on category, bedrooms, and area."""

    limit = max(1, min(limit or 6, 12))
    category_ids = [c.id for c in getattr(plan, 'categories', [])]
    beds_value = plan.bedrooms_count or plan.number_of_bedrooms or plan.bedrooms or 0
    area_value = plan.area_sqft or plan.total_area_sqft or plan.square_feet or 0

    query = (
        HousePlan.query
        .filter(HousePlan.is_published.is_(True))
        .filter(HousePlan.id != plan.id)
        .options(selectinload(HousePlan.categories))
    )

    if category_ids:
        query = query.join(HousePlan.categories).filter(Category.id.in_(category_ids))

    if beds_value:
        beds_expr = func.coalesce(HousePlan.number_of_bedrooms, HousePlan.bedrooms, 0)
        query = query.filter(func.abs(beds_expr - beds_value) <= 1)

    area_expr = func.coalesce(HousePlan.total_area_sqft, cast(HousePlan.square_feet, Float), 0.0)
    uses_distance = False
    if area_value:
        window = float(area_value)
        lower = max(0.0, window * 0.8)
        upper = window * 1.2
        distance_expr = func.abs(area_expr - window).label('area_distance')
        query = query.filter(area_expr.between(lower, upper))
        query = query.add_columns(distance_expr)
        query = query.order_by(distance_expr.asc(), HousePlan.views_count.desc())
        uses_distance = True
    else:
        query = query.order_by(HousePlan.views_count.desc(), HousePlan.created_at.desc())

    if category_ids:
        query = query.distinct()

    results = query.limit(limit).all()
    if uses_distance:
        return [row[0] for row in results]
    return results


def _serialize_plan_summary(plan: HousePlan):
    cover_image = plan.cover_image or plan.main_image or ''
    area_raw = getattr(plan, 'area_sqft', None) or getattr(plan, 'total_area_sqft', None) or getattr(plan, 'square_feet', None)
    beds_raw = getattr(plan, 'bedrooms_count', None) or getattr(plan, 'number_of_bedrooms', None) or getattr(plan, 'bedrooms', None)
    try:
        area_value = float(area_raw) if area_raw else None
    except (TypeError, ValueError):
        area_value = None
    try:
        bedrooms_value = int(beds_raw) if beds_raw else None
    except (TypeError, ValueError):
        bedrooms_value = None
    return {
        'slug': plan.slug,
        'title': plan.title,
        'reference': plan.reference_code,
        'thumb': url_for('static', filename=cover_image) if cover_image else '',
        'area': area_value,
        'bedrooms': bedrooms_value,
        'starting_price': plan.starting_paid_price,
    }


@main_bp.route('/download/free/<int:plan_id>')
def download_free(plan_id):
    """Serve free PDF for a plan without login, but from protected storage."""
    plan = HousePlan.query.get_or_404(plan_id)
    if not plan.free_pdf_file:
        abort(404)

    if is_absolute_url(plan.free_pdf_file):
        url_value = plan.free_pdf_file or ''
        url_path = url_value.split('?')[0].lower()
        if not url_path.endswith('.pdf'):
            parsed = urlparse(url_value)
            host = (parsed.hostname or '').lower()
            is_cloudinary = host.endswith('cloudinary.com')
            if not is_cloudinary:
                current_app.logger.warning('Blocked non-PDF free download URL for plan %s: %s', plan.id, plan.free_pdf_file)
                abort(400)
        return redirect(plan.free_pdf_file)

    try:
        protected_path = resolve_protected_upload(plan.free_pdf_file)
    except ValueError as exc:
        current_app.logger.warning('Invalid protected file path for plan %s: %s', plan.id, exc)
        abort(400)

    if not protected_path.exists():
        abort(404)

    is_pdf = protected_path.suffix.lower() == '.pdf'
    if not is_pdf:
        try:
            with protected_path.open('rb') as handle:
                header = handle.read(4)
            is_pdf = header == b'%PDF'
        except Exception as exc:
            current_app.logger.warning('Failed to inspect free download for plan %s: %s', plan.id, exc)
            abort(400)

    if not is_pdf:
        current_app.logger.warning('Blocked non-PDF free download for plan %s: %s', plan.id, protected_path)
        abort(400)

    return send_file(
        protected_path,
        as_attachment=True,
        download_name=f"{protected_path.stem}.pdf",
        mimetype='application/pdf'
    )


def _is_allowed_gumroad_url(raw_url: str) -> bool:
    if not raw_url:
        return False
    try:
        parsed = urlparse(raw_url.strip())
    except Exception:
        return False
    if parsed.scheme not in ('https', 'http'):
        return False
    host = (parsed.hostname or '').lower()
    # Allow Gumroad domains and the official short-link domain.
    return host == 'gumroad.com' or host.endswith('.gumroad.com') or host == 'gum.co'


@main_bp.route('/go/<slug>/<int:pack>')
def gumroad_redirect(slug, pack):
    """Redirect users to the Gumroad checkout for paid packs.

    Business rule: Pack 2 and 3 are sold via Gumroad links only.
    """
    if pack not in (2, 3):
        abort(404)
    plan = HousePlan.query.filter_by(slug=slug, is_published=True).first_or_404()
    target = plan.gumroad_pack_2_url if pack == 2 else plan.gumroad_pack_3_url
    if not target:
        flash('This pack is not available yet.', 'warning')
        return redirect(url_for('main.pack_detail', slug=plan.slug))
    if not _is_allowed_gumroad_url(target):
        current_app.logger.warning('Blocked non-Gumroad redirect for plan=%s pack=%s', plan.id, pack)
        abort(400)
    return redirect(target)


@main_bp.route('/')
def index():
    """Homepage route"""
    
    try:
        # Get featured plans
        featured_plans = HousePlan.query.filter_by(
            is_published=True,
            is_featured=True
        ).limit(6).all()
        
        # Get recent plans
        recent_plans = HousePlan.query.filter_by(
            is_published=True
        ).order_by(HousePlan.created_at.desc()).limit(8).all()
    except Exception as e:
        current_app.logger.warning(f'Database query failed on homepage: {e}. Returning empty results.')
        featured_plans = []
        recent_plans = []
    
    # SEO meta tags
    meta = generate_meta_tags(
        title='Home',
        description='Browse our collection of premium architectural house plans for your dream home',
        url=url_for('main.index', _external=True)
    )
    
    return render_template('home.html',
                         featured_plans=featured_plans,
                         recent_plans=recent_plans,
                         meta=meta)


@main_bp.route('/plans')
def packs():
    """House plans listing page with filtering and pagination"""

    try:
        page = request.args.get('page', 1, type=int)
        per_page = current_app.config.get('PLANS_PER_PAGE', 12)
        query = _build_catalog_query(request.args)
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        plans = pagination.items
        narrative_key = request.args.get('narrative', '').strip()
        narrative_meta = NARRATIVE_FILTERS.get(narrative_key)
        
        # Filter metadata
        categories = Category.query.order_by(Category.name.asc()).all()
        plan_types = [
            row[0]
            for row in (
                db.session.query(HousePlan.plan_type)
                .filter(HousePlan.is_published.is_(True))
                .filter(HousePlan.plan_type.isnot(None))
                .distinct()
                .order_by(HousePlan.plan_type.asc())
                .all()
            )
            if row[0]
        ]

        result_summary = f"{pagination.total} plan{'s' if pagination.total != 1 else ''} available"
        if narrative_meta:
            result_summary += f" · {narrative_meta['label']}"

        popular_plans = _get_popular_plans()
        new_arrivals = _get_new_arrivals()
        climate_focus = _get_climate_focus()

        suggestion_targets = popular_plans[:2] or new_arrivals[:2]
    except Exception as e:
        current_app.logger.warning(f'Database query failed on plans page: {e}. Returning empty results.')
        pagination = None
        plans = []
        categories = []
        plan_types = []
        result_summary = "No plans available"
        narrative_meta = None
        narrative_key = ''
        popular_plans = []
        new_arrivals = []
        climate_focus = []
        suggestion_targets = []
    
    # SEO meta tags
    meta = generate_meta_tags(
        title='House Plans',
        description='Browse our complete collection of architectural house plans',
        url=url_for('main.packs', _external=True)
    )
    
    return render_template('packs.html',
                         plans=plans,
                         pagination=pagination,
                         categories=categories,
                         plan_types=plan_types,
                         result_summary=result_summary,
                         narrative_filters=NARRATIVE_FILTERS,
                         active_narrative=narrative_key,
                         popular_plans=popular_plans,
                         new_arrivals=new_arrivals,
                         climate_focus=climate_focus,
                         suggestion_targets=suggestion_targets,
                         guides=GUIDE_ARTICLES,
                         meta=meta)


@main_bp.route('/plans/fragment')
def plans_fragment():
    """HTML fragment endpoint for progressively loading more plans."""

    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('PLANS_PER_PAGE', 12)
    query = _build_catalog_query(request.args)

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    html = render_template('_plan_cards.html', plans=pagination.items)
    resp = Response(html, mimetype='text/html')
    resp.headers['X-Has-Next'] = '1' if pagination.has_next else '0'
    resp.headers['X-Next-Page'] = str(pagination.next_num) if pagination.has_next else ''
    return resp


@main_bp.route('/plans/data')
def plans_data():
    """JSON endpoint powering real-time catalog filtering."""

    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('PLANS_PER_PAGE', 12)
    query = _build_catalog_query(request.args)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    cards_html = render_template('_plan_cards.html', plans=pagination.items)
    pagination_html = ''
    if pagination.pages > 1:
        pagination_html = render_template('_pagination.html', pagination=pagination, endpoint='main.packs')

    summary_text = f"{pagination.total} plan{'s' if pagination.total != 1 else ''} available"

    payload = {
        'cardsHtml': cards_html,
        'paginationHtml': pagination_html,
        'hasResults': bool(pagination.items),
        'hasNext': pagination.has_next,
        'nextPage': pagination.next_num if pagination.has_next else None,
        'page': pagination.page,
        'pages': pagination.pages,
        'total': pagination.total,
        'summaryText': summary_text,
    }
    return jsonify(payload)


@main_bp.route('/plans/similar/<string:slug>')
def plans_similar(slug: str):
    """Return similar plans for personalization rails."""

    limit = request.args.get('limit', 6, type=int)
    plan = (
        HousePlan.query
        .options(selectinload(HousePlan.categories))
        .filter_by(slug=slug, is_published=True)
        .first_or_404()
    )
    similar = _find_similar_plans(plan, limit=limit)
    return jsonify({'plans': [_serialize_plan_summary(p) for p in similar]})


@main_bp.route('/plans/category/<string:slug>')
def plans_by_category(slug: str):
    category = Category.query.filter_by(slug=slug).first_or_404()
    categories = Category.query.order_by(Category.name.asc()).all()
    plans = (
        HousePlan.query
        .filter_by(is_published=True)
        .join(HousePlan.categories)
        .filter(Category.id == category.id)
        .all()
    )

    # Simple SEO meta derived from DB content (no hardcoding)
    seo_title = f"{category.name} House Plans"
    if category.description:
        seo_description = category.description
    else:
        seo_description = f"Browse free {category.name.lower()} house plans with floor plans, images, and details."

    meta = generate_meta_tags(
        title=seo_title,
        description=seo_description,
        url=url_for('main.plans_by_category', slug=category.slug, _external=True),
    )

    item_list_elements = []
    for idx, plan in enumerate(plans[:20], start=1):
        item_list_elements.append({
            "@type": "ListItem",
            "position": idx,
            "url": url_for('main.pack_detail', slug=plan.slug, _external=True),
            "name": plan.title,
        })

    category_schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": seo_title,
        "description": seo_description,
        "url": url_for('main.plans_by_category', slug=category.slug, _external=True),
        "about": category.description or f"{category.name} house plans",
        "itemList": {
            "@type": "ItemList",
            "name": f"{category.name} plans",
            "numberOfItems": len(plans),
            "itemListElement": item_list_elements,
        },
    }

    return render_template(
        'plans_by_category.html',
        category=category,
        categories=categories,
        plans=plans,
        meta=meta,
        category_schema=category_schema,
    )

@main_bp.route('/insights/<string:slug>')
def insight_page(slug):
    article = GUIDE_ARTICLES.get(slug)
    if not article:
        abort(404)

    related = _get_new_arrivals(limit=4)

    meta = generate_meta_tags(
        title=article['title'],
        description=article['description'],
        url=url_for('main.insight_page', slug=slug, _external=True),
    )

    return render_template(
        'insight_page.html',
        article=article,
        slug=slug,
        related_plans=related,
        meta=meta,
    )


@main_bp.route('/plan/<slug>')
def pack_detail(slug):
    """Public plan detail page.

    This route must never 500 due to missing optional fields or relationships.
    """

    def _rollback_safely(reason: str):
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            current_app.logger.warning('Rolled back session (%s) to clear failed transaction.', reason)
        except Exception:
            pass

    plan = None
    try:
        # Support legacy /plan/<id> links even though the canonical URL is /plan/<slug>.
        if slug and str(slug).isdigit():
            plan_id = int(slug)
            plan = db.session.get(HousePlan, plan_id)
            if plan is None:
                abort(404)
        else:
            plan = (
                db.session.query(HousePlan)
                .options(selectinload(HousePlan.categories))
                .filter_by(slug=slug)
                .first_or_404()
            )

        # Only public plans should be visible.
        if not getattr(plan, 'is_published', False):
            abort(404)

        category_name = plan.category.name if getattr(plan, 'category', None) else 'Uncategorized'

        print(f'DEBUG: pack_detail slug={slug!r} resolved plan id={getattr(plan, "id", None)} title={getattr(plan, "title", None)!r}')
        print(f'DEBUG: pack_detail plan has category? {bool(getattr(plan, "category", None))}')

        # Increment view count (non-fatal).
        try:
            plan.increment_views()
        except Exception as view_exc:
            _rollback_safely('increment_views')
            current_app.logger.warning('Failed to increment view count for plan id=%s: %s', getattr(plan, 'id', None), view_exc)

        similar_plans = []
        try:
            similar_plans = _find_similar_plans(plan, limit=6)
        except Exception as similar_exc:
            _rollback_safely('similar_plans')
            current_app.logger.warning('Failed to load similar plans for plan id=%s: %s', getattr(plan, 'id', None), similar_exc)

        meta = None
        try:
            meta = generate_meta_tags(
                title=getattr(plan, 'meta_title', None) or plan.title,
                description=getattr(plan, 'meta_description', None) or getattr(plan, 'short_description', None) or '',
                keywords=getattr(plan, 'meta_keywords', None),
                url=url_for('main.pack_detail', slug=getattr(plan, 'slug', slug), _external=True),
                type='product'
            )
        except Exception as meta_exc:
            current_app.logger.warning('Failed to generate meta tags for plan id=%s: %s', getattr(plan, 'id', None), meta_exc)
            meta = generate_meta_tags(title=getattr(plan, 'title', 'House Plan'), url=url_for('main.packs', _external=True), type='product')

        product_schema = None
        try:
            product_schema = generate_product_schema(plan)
        except Exception as schema_exc:
            current_app.logger.warning('Failed to generate product schema for plan id=%s: %s', getattr(plan, 'id', None), schema_exc)

        # FAQs: prefer custom FAQs attached to the plan; if none, use defaults.
        faqs = []
        faq_schema = None
        try:
            if getattr(plan, 'faqs', None):
                faqs = list(plan.faqs) if plan.faqs else []
            if not faqs and hasattr(plan, 'default_faqs'):
                faqs = plan.default_faqs()

            if faqs:
                faq_schema = {
                    '@context': 'https://schema.org',
                    '@type': 'FAQPage',
                    'mainEntity': []
                }
                for item in faqs:
                    try:
                        if hasattr(item, 'question'):
                            q = item.question
                            a = item.answer
                        else:
                            q = item.get('question')
                            a = item.get('answer')
                        if q and a:
                            faq_schema['mainEntity'].append({
                                '@type': 'Question',
                                'name': q,
                                'acceptedAnswer': {
                                    '@type': 'Answer',
                                    'text': a
                                }
                            })
                    except Exception:
                        continue
        except Exception as faq_exc:
            _rollback_safely('faqs')
            current_app.logger.warning('Failed to load FAQs for plan id=%s: %s', getattr(plan, 'id', None), faq_exc)
            faqs = []
            faq_schema = None

        breadcrumb_schema = None
        try:
            breadcrumbs = [
                ('Home', url_for('main.index')),
                ('Plans', url_for('main.packs')),
                (getattr(plan, 'title', 'House Plan'), url_for('main.pack_detail', slug=getattr(plan, 'slug', slug)))
            ]
            breadcrumb_schema = generate_breadcrumb_schema(breadcrumbs)
        except Exception as breadcrumb_exc:
            current_app.logger.warning('Failed to generate breadcrumb schema for plan id=%s: %s', getattr(plan, 'id', None), breadcrumb_exc)

        return render_template(
            'pack_detail.html',
            plan=plan,
            category_name=category_name,
            faqs=faqs,
            faq_schema=faq_schema,
            similar_plans=similar_plans,
            meta=meta,
            product_schema=product_schema,
            breadcrumb_schema=breadcrumb_schema,
        )

    except HTTPException:
        raise
    except SQLAlchemyError as db_exc:
        try:
            db.session.rollback()
        except Exception as rollback_exc:
            current_app.logger.error('Rollback failed after pack_detail DB error: %s', rollback_exc, exc_info=True)
        print(traceback.format_exc())
        current_app.logger.error('pack_detail DB error slug=%s: %s', slug, db_exc, exc_info=True)
        return Response('Plan temporarily unavailable. Please try again later.', status=503)
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception as rollback_exc:
            current_app.logger.error('Rollback failed after pack_detail error: %s', rollback_exc, exc_info=True)
        print(traceback.format_exc())
        current_app.logger.error('pack_detail failed slug=%s: %s', slug, exc, exc_info=True)
        return Response('Plan temporarily unavailable. Please try again later.', status=503)


@main_bp.route('/plan/id/<int:id>')
def plan_detail_by_id(id: int):
    """ID-based plan detail entrypoint.

    Useful when links are built from DB IDs. Redirects to canonical slug URL.
    """

    try:
        plan = db.session.get(HousePlan, id)
        if plan is None:
            abort(404)
        return redirect(url_for('main.pack_detail', slug=plan.slug), code=302)
    except HTTPException:
        raise
    except SQLAlchemyError as db_exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        print(traceback.format_exc())
        current_app.logger.error('Plan detail DB error for ID %s: %s', id, db_exc, exc_info=True)
        return Response('Plan temporarily unavailable. Please try again later.', status=503)
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        print(traceback.format_exc())
        current_app.logger.error('Plan detail error for ID %s: %s', id, e, exc_info=True)
        return Response('Plan temporarily unavailable. Please try again later.', status=503)


@main_bp.route('/plans/<int:plan_id>')
def plan_detail(plan_id: int):
    """Plan detail page (ID-based).

    Requirements:
        - Uses db.session.get(HousePlan, plan_id)
        - Wraps render in try/except; on error logs via app.logger.error(), rolls back,
            and returns a clear error message instead of a generic 500 page.
    """

    try:
        plan = db.session.get(HousePlan, plan_id)
        if plan is None:
            abort(404)

        # Only public plans should be visible.
        if not getattr(plan, 'is_published', False):
            abort(404)

        print(f'DEBUG: Plan ID {plan_id} found: {plan}')
        print(f'DEBUG: Plan ID {plan_id} category exists: {bool(getattr(plan, "category", None))}')

        meta = generate_meta_tags(
            title=getattr(plan, 'meta_title', None) or getattr(plan, 'title', 'House Plan'),
            description=getattr(plan, 'meta_description', None) or getattr(plan, 'short_description', None) or '',
            keywords=getattr(plan, 'meta_keywords', None),
            url=url_for('main.plan_detail', plan_id=getattr(plan, 'id', plan_id), _external=True),
            type='product'
        )
        return render_template('plan_detail.html', plan=plan, meta=meta)

    except HTTPException:
        raise
    except SQLAlchemyError as db_exc:
        try:
            db.session.rollback()
        except Exception as rollback_exc:
            current_app.logger.error('Rollback failed after plan detail DB error: %s', rollback_exc, exc_info=True)
        print(traceback.format_exc())
        current_app.logger.error('Plan detail DB error for id=%s: %s', plan_id, db_exc, exc_info=True)
        return Response('Plan temporarily unavailable. Please try again later or contact support.', status=503)
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception as rollback_exc:
            current_app.logger.error('Rollback failed after plan detail error: %s', rollback_exc, exc_info=True)
        print(traceback.format_exc())
        current_app.logger.error('Plan detail rendering failed for id=%s: %s', plan_id, exc, exc_info=True)
        return Response('Plan temporarily unavailable. Please try again later or contact support.', status=503)


@main_bp.route('/favorites')
def favorites():
    """Client-side favorites page (localStorage powered)."""

    meta = generate_meta_tags(
        title='My Favorites',
        description='Save house plans you love and revisit them anytime on this device.',
        url=url_for('main.favorites', _external=True),
    )

    return render_template('favorites.html', meta=meta)


@main_bp.route('/compare')
def compare():
    """Client-side comparison landing page."""

    meta = generate_meta_tags(
        title='Compare House Plans',
        description='Select up to three house plans and review their specs, areas, and pack pricing side by side.',
        url=url_for('main.compare', _external=True),
    )

    return render_template('compare.html', meta=meta)


@main_bp.route('/compare/data')
def compare_data():
    slugs_param = (request.args.get('slugs') or '').strip()
    if not slugs_param:
        return jsonify({'plans': []})

    slugs = []
    for chunk in slugs_param.split(','):
        slug = chunk.strip()
        if not slug:
            continue
        if slug in slugs:
            continue
        slugs.append(slug)
        if len(slugs) >= 3:
            break

    if not slugs:
        return jsonify({'plans': []})

    plans = (
        HousePlan.query
        .filter(HousePlan.slug.in_(slugs), HousePlan.is_published == True)
        .options(selectinload(HousePlan.categories))
        .all()
    )

    pack_visibility = load_pack_visibility()

    plan_lookup = {}
    for plan in plans:
        tiers = []
        for tier in filter_pack_tiers(plan.pricing_tiers, pack_visibility):
            price = tier.get('price')
            try:
                normalized_price = float(price) if price is not None else None
            except (TypeError, ValueError):
                normalized_price = None
            tiers.append({
                'pack': tier.get('pack'),
                'label': tier.get('label'),
                'price': normalized_price,
                'is_free': tier.get('is_free'),
                'available': tier.get('available'),
            })

        plan_lookup[plan.slug] = {
            'slug': plan.slug,
            'title': plan.title,
            'reference_code': plan.reference_code,
            'area_sqft': plan.area_sqft,
            'area_m2': plan.area_m2,
            'bedrooms': plan.bedrooms_count,
            'bathrooms': plan.bathrooms_count,
            'plan_type': plan.plan_type,
            'categories': [c.name for c in plan.categories] if plan.categories else [],
            'starting_price': plan.starting_paid_price,
            'tiers': tiers,
        }

    ordered = [plan_lookup[slug] for slug in slugs if slug in plan_lookup]
    return jsonify({'plans': ordered})


@main_bp.route('/newsletter', methods=['POST'])
def newsletter_signup():
    payload = request.get_json(silent=True) or request.form
    email = (payload.get('email') if payload else '') or ''
    email = email.strip()
    if not email:
        return jsonify({'ok': False, 'message': 'Please enter an email.'}), 400

    record = ContactMessage(
        name='Newsletter subscriber',
        email=email,
        phone=None,
        subject='Newsletter opt-in',
        message='Newsletter signup via public form',
        inquiry_type='newsletter',
        subscribe=True,
    )
    try:
        db.session.add(record)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.warning('Failed to save newsletter signup: %s', exc)
        return jsonify({'ok': False, 'message': 'We could not save your signup right now.'}), 500

    success_msg = 'Thanks! We will notify you as soon as a new plan is published.'
    if request.headers.get('X-Requested-With') == 'fetch' or request.accept_mimetypes.accept_json:
        return jsonify({'ok': True, 'message': success_msg})

    flash(success_msg, 'success')
    return redirect(request.referrer or url_for('main.packs'))


@main_bp.route('/about')
def about():
    """About page"""
    
    meta = generate_meta_tags(
        title='About',
        description='Learn how MyFreeHousePlans works, what’s included in each pack, and how we support your build.',
        url=url_for('main.about', _external=True)
    )
    
    return render_template('about.html', meta=meta)


@main_bp.route('/faq')
def faq():
    """Frequently asked questions page"""
    meta = generate_meta_tags(
        title='FAQ',
        description='Frequently asked questions about MyFreeHousePlans — plans, purchases, downloads, and licensing.',
        url=url_for('main.faq', _external=True)
    )

    faqs = [
        {'q': 'How do I purchase a plan?', 'a': 'Choose a plan from the catalog, follow the purchase link, and you will receive download instructions after payment.'},
        {'q': 'What is included in a plan pack?', 'a': 'Every pack contains a set of PDF drawings, a dimensioned floor plan, elevations, and a basic materials list. Some packs include CAD files or multiple size options.'},
        {'q': 'Can I modify a plan for my site?', 'a': 'Yes — plans can be adapted by a local architect or designer. We recommend hiring a licensed professional to ensure compliance with local codes.'},
        {'q': 'Are these plans compliant with local building codes?', 'a': 'Plans are created as general construction documents. Local code compliance, site-specific adjustments, and structural engineering are the purchaser’s responsibility.'},
        {'q': 'Which file formats do you provide?', 'a': 'Most packs include high-resolution PDF files; many also include DWG/CAD files or SketchUp models when noted on the plan page.'},
        {'q': 'How do I download my purchase?', 'a': 'After payment you will receive a download link via email and on the purchase confirmation page. Save the files and back them up.'},
        {'q': 'What is your refund policy?', 'a': 'We offer refunds for mistaken purchases within a short window. Custom work and modified downloads are generally non-refundable — contact support for details.'},
        {'q': 'Can I request additional documentation or permit sets?', 'a': 'We can produce extended documentation for an additional fee. Contact us with the plan reference code and your requirements.'},
        {'q': 'How does licensing work for builders?', 'a': 'Our plans are sold per-project; commercial or multi-build licenses are available. See our terms or contact sales for licensing options.'},
        {'q': 'How do I get support or ask a question?', 'a': 'Email entreprise2rc@gmail.com or use the contact form. We typically reply within 1–3 business days.'},
    ]

    return render_template('faq.html', meta=meta, faqs=faqs)

@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact page with form"""
    
    form = ContactForm()
    try:
        plan_options = (
            HousePlan.query.filter_by(is_published=True)
            .order_by(HousePlan.title.asc())
            .all()
        )
        plan_choices = [('', 'Not sure yet')]
        plan_map = {}
        for plan in plan_options:
            label = f"{plan.title} · {plan.reference_code}"
            plan_choices.append((str(plan.id), label))
            plan_map[str(plan.id)] = plan
        form.plan_reference.choices = plan_choices
    except Exception as e:
        current_app.logger.warning(f'Database query failed on contact page: {e}. Using empty plan options.')
        plan_options = []
        plan_choices = [('', 'Not sure yet')]
        form.plan_reference.choices = plan_choices
        plan_map = {}
    if request.method == 'GET':
        form.subject.data = form.subject.data or 'General contact request'
        form.inquiry_type.data = form.inquiry_type.data or 'support'
    
    meta = generate_meta_tags(
        title='Contact',
        description='Contact MyFreeHousePlans for plan questions, pack details, or Gumroad purchase support.',
        url=url_for('main.contact', _external=True)
    )
    
    if form.validate_on_submit():
        selected_plan = plan_map.get(form.plan_reference.data)
        plan_label = f"{selected_plan.title} ({selected_plan.reference_code})" if selected_plan else None

        saved_attachment = None
        attachment_absolute = None
        attachment_mime = None
        attachment_obj = form.attachment.data
        if attachment_obj and getattr(attachment_obj, 'filename', ''):
            try:
                saved_attachment = save_uploaded_file(attachment_obj, 'support')
                attachment_absolute = resolve_protected_upload(saved_attachment)
                attachment_mime, _ = mimetypes.guess_type(str(attachment_absolute))
            except ValueError as upload_err:
                current_app.logger.warning('Upload failed while handling contact attachment: %s', upload_err)
                flash("We couldn't upload that file. Please ensure it's a supported file type and under 16 MB, then try again.", 'danger')
                return render_template('contact.html', form=form, meta=meta, plan_options=plan_options)
            except Exception as exc:
                current_app.logger.exception('Unexpected error resolving protected upload: %s', exc)
                flash('We could not store that attachment. Please try again with a different file.', 'danger')
                return render_template('contact.html', form=form, meta=meta, plan_options=plan_options)

        message_record = ContactMessage(
            name=(form.name.data or '').strip(),
            email=(form.email.data or '').strip(),
            phone=(form.phone.data or '').strip() or None,
            subject=(form.subject.data or '').strip(),
            message=form.message.data.strip(),
            inquiry_type=form.inquiry_type.data,
            reference_code=(form.reference_code.data or '').strip() or None,
            subscribe=bool(form.subscribe.data),
            plan_id=selected_plan.id if selected_plan else None,
            plan_snapshot=plan_label,
            attachment_path=saved_attachment,
            attachment_name=getattr(attachment_obj, 'filename', None),
            attachment_mime=attachment_mime,
        )

        try:
            db.session.add(message_record)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception('Failed to store contact message: %s', exc)
            flash("We're sorry — we couldn't save your message right now. Please try again shortly or email entreprise2rc@gmail.com and we'll assist you.", 'danger')
            return render_template('contact.html', form=form, meta=meta, plan_options=plan_options)

        # Guaranteed user confirmation: always show success immediately after DB commit.
        success_message = 'Thank you! Your message has been sent. We will get back to you shortly.'
        # For XHR/JSON clients, return JSON success response.
        if request.headers.get('X-Requested-With') == 'fetch' or request.accept_mimetypes.accept_json:
            # Attempt background-safe email operations but do not block response.
            try:
                # Send admin notification (best-effort)
                admin_email_sent = False
                email_error_text = None
                try:
                    msg = MailMessage(
                        subject=f"Contact Form: {form.subject.data}",
                        recipients=[current_app.config.get('ADMIN_EMAIL')],
                        reply_to=form.email.data
                    )
                    msg.body = (
                        f"New contact form submission (Message #{message_record.id}):\n\n"
                        f"Name: {form.name.data}\n"
                        f"Email: {form.email.data}\n"
                        f"Phone: {form.phone.data or 'Not provided'}\n"
                        f"Subject: {form.subject.data}\n"
                        f"Inquiry type: {form.inquiry_type.data}\n"
                        f"Plan interest: {plan_label or 'Not provided'}\n"
                        f"Reference code provided: {form.reference_code.data or 'Not provided'}\n"
                        f"Opt-in to updates: {'Yes' if form.subscribe.data else 'No'}\n"
                        f"Attachment path: {saved_attachment or 'None'}\n\n"
                        f"Message:\n{form.message.data}\n"
                    )
                    if attachment_absolute and attachment_absolute.exists():
                        with attachment_absolute.open('rb') as handle:
                            msg.attach(
                                attachment_absolute.name,
                                attachment_mime or 'application/octet-stream',
                                handle.read()
                            )
                    mail.send(msg)
                    admin_email_sent = True
                except Exception as exc:
                    email_error_text = str(exc)
                    current_app.logger.error('Failed to send contact email for message %s: %s', message_record.id, exc)

                message_record.email_status = ContactMessage.EMAIL_SENT if admin_email_sent else ContactMessage.EMAIL_FAILED
                message_record.email_error = None if admin_email_sent else (email_error_text or 'Delivery failed')
                message_record.status_updated_at = datetime.utcnow()
                try:
                    db.session.commit()
                except Exception as exc:
                    db.session.rollback()
                    current_app.logger.exception('Failed to update contact message %s delivery status: %s', message_record.id, exc)

                # Send acknowledgment to the user (best-effort)
                try:
                    ack = MailMessage(
                        subject='We received your message',
                        recipients=[message_record.email],
                    )
                    ack.body = (
                        f"Hi {message_record.name},\n\n"
                        "Thanks for contacting MyFreeHousePlans. We've logged your request with our studio inbox. "
                        "Someone will respond within two business days."
                        f"\n\nReference: Message #{message_record.id}\n"
                        "If you need immediate assistance, reply to this email or reach out at entreprise2rc@gmail.com."
                        "\n\n— Studio Support"
                    )
                    mail.send(ack)
                except Exception as exc:
                    current_app.logger.warning('Failed to send acknowledgment for message %s: %s', message_record.id, exc)
            except Exception:
                # Ensure no exceptions escape to the client for XHR flows.
                current_app.logger.exception('Unexpected error in post-save email flow for message %s', message_record.id)
            return jsonify({'ok': True, 'message': success_message})

        # Non-XHR flow: show guaranteed confirmation and continue to best-effort delivery.
        flash(success_message, 'success')

        # Best-effort admin notification: log failures, do NOT block user flow.
        admin_email_sent = False
        email_error_text = None
        try:
            try:
                msg = MailMessage(
                    subject=f"Contact Form: {form.subject.data}",
                    recipients=[current_app.config.get('ADMIN_EMAIL')],
                    reply_to=form.email.data
                )
                msg.body = (
                    f"New contact form submission (Message #{message_record.id}):\n\n"
                    f"Name: {form.name.data}\n"
                    f"Email: {form.email.data}\n"
                    f"Phone: {form.phone.data or 'Not provided'}\n"
                    f"Subject: {form.subject.data}\n"
                    f"Inquiry type: {form.inquiry_type.data}\n"
                    f"Plan interest: {plan_label or 'Not provided'}\n"
                    f"Reference code provided: {form.reference_code.data or 'Not provided'}\n"
                    f"Opt-in to updates: {'Yes' if form.subscribe.data else 'No'}\n"
                    f"Attachment path: {saved_attachment or 'None'}\n\n"
                    f"Message:\n{form.message.data}\n"
                )
                if attachment_absolute and attachment_absolute.exists():
                    with attachment_absolute.open('rb') as handle:
                        msg.attach(
                            attachment_absolute.name,
                            attachment_mime or 'application/octet-stream',
                            handle.read()
                        )
                mail.send(msg)
                admin_email_sent = True
            except Exception as exc:
                email_error_text = str(exc)
                current_app.logger.error('Failed to send contact email for message %s: %s', message_record.id, exc)

            message_record.email_status = ContactMessage.EMAIL_SENT if admin_email_sent else ContactMessage.EMAIL_FAILED
            message_record.email_error = None if admin_email_sent else (email_error_text or 'Delivery failed')
            message_record.status_updated_at = datetime.utcnow()
            try:
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                current_app.logger.exception('Failed to update contact message %s delivery status: %s', message_record.id, exc)

            try:
                ack = MailMessage(
                    subject='We received your message',
                    recipients=[message_record.email],
                )
                ack.body = (
                    f"Hi {message_record.name},\n\n"
                    "Thanks for contacting MyFreeHousePlans. We've logged your request with our studio inbox. "
                    "Someone will respond within two business days."
                    f"\n\nReference: Message #{message_record.id}\n"
                    "If you need immediate assistance, reply to this email or reach out at entreprise2rc@gmail.com."
                    "\n\n— Studio Support"
                )
                mail.send(ack)
            except Exception as exc:
                current_app.logger.warning('Failed to send acknowledgment for message %s: %s', message_record.id, exc)

        except Exception:
            current_app.logger.exception('Unexpected error in post-save email flow for message %s', message_record.id)

        tag_visit_identity(name=message_record.name, email=message_record.email)
        return redirect(url_for('main.contact'))
    
    return render_template('contact.html', form=form, meta=meta, plan_options=plan_options)


@main_bp.route('/privacy-policy')
def privacy_policy():
    """Google-compliant privacy policy page."""

    sections = [
        {
            'title': 'Data Collection',
            'body': [
                'My Free House Plans collects the information you provide when you browse the catalog, create an account, or submit a form. Typical data includes your name, email address, plan preferences, files you upload, and aggregated analytics collected through our site.',
                'Purchase workflows managed through partners such as Gumroad share limited order metadata with us so we can deliver downloads and support.'
            ],
        },
        {
            'title': 'Cookies & Local Storage',
            'body': [
                'We use strictly necessary cookies to keep your favorites list and comparison tray synced across sessions. Optional analytics cookies measure which plans perform well so we can improve the catalog.',
                'You can clear or block cookies at any time through your browser. Doing so may reset saved preferences such as language, currency, or shortlisted plans.'
            ],
        },
        {
            'title': 'Google AdSense Disclosure',
            'body': [
                'Third-party vendors, including Google, use cookies to serve ads based on your prior visits to My Free House Plans or other websites.',
                'Google’s use of advertising cookies enables it and its partners to serve ads based on your visit to our site and other sites on the internet. You may opt out of personalized advertising by visiting Google’s Ads Settings or aboutads.info.'
            ],
        },
        {
            'title': 'Your Rights & Requests',
            'body': [
                'You can request a copy of the personal data we store, ask for corrections, or request deletion of non-essential records. We honor valid privacy requests within 30 days.',
                'To exercise any right or raise a question, contact us at entreprise2rc@gmail.com or through the contact form on this site.'
            ],
        },
    ]

    meta = generate_meta_tags(
        title='Privacy Policy',
        description='Understand how My Free House Plans handles analytics, cookies, Google AdSense data, and user privacy requests.',
        url=url_for('main.privacy_policy', _external=True)
    )

    return render_template('privacy_policy.html', meta=meta, sections=sections, last_updated=datetime.utcnow().date())


@main_bp.route('/privacy')
def privacy():
    """Backward-compatible alias for legacy /privacy."""
    return redirect(url_for('main.privacy_policy'), code=301)


@main_bp.route('/terms-of-service')
def terms_of_service():
    """Google-compliant terms of service page."""

    clauses = [
        {
            'title': 'Intellectual Property',
            'body': [
                'All house plans, images, CAD files, and written content published on My Free House Plans remain the exclusive intellectual property of the studio or its licensors.',
                'Purchasing a plan grants you a single-use, non-transferable license to construct one project. Reproduction, resale, or distribution of plan files without written permission is prohibited.'
            ],
        },
        {
            'title': 'Limitation of Liability',
            'body': [
                'House plans are provided “as-is” for informational and design inspiration purposes. Field conditions, local codes, soil reports, and engineering requirements may require modifications by licensed professionals.',
                'My Free House Plans and its contributors are not liable for direct or indirect damages arising from the use of any plan, document, or consultation offered on this site.'
            ],
        },
        {
            'title': 'External Links & Third Parties',
            'body': [
                'Our catalog links to partners such as Gumroad for secure checkout and download fulfillment. We are not responsible for the content, policies, or availability of external websites.',
                'When you leave our domain, review the destination’s policies to understand how your information will be handled.'
            ],
        },
    ]

    meta = generate_meta_tags(
        title='Terms of Service',
        description='Review the license, limitations, and third-party policies that govern your use of My Free House Plans.',
        url=url_for('main.terms_of_service', _external=True)
    )

    return render_template('terms_of_service.html', meta=meta, clauses=clauses, last_updated=datetime.utcnow().date())


@main_bp.route('/terms')
def terms():
    """Backward-compatible alias for legacy /terms."""
    return redirect(url_for('main.terms_of_service'), code=301)


@main_bp.route('/sitemap.xml')
def sitemap():
    """Generate XML sitemap for SEO"""
    
    # Get all published plans
    plans = HousePlan.query.filter_by(is_published=True).all()
    
    # Get all categories
    categories = Category.query.all()
    
    # Generate sitemap XML
    sitemap_xml = generate_sitemap(plans, categories)
    
    return Response(sitemap_xml, mimetype='application/xml')


@main_bp.route('/robots.txt')
def robots():
    """Generate robots.txt file"""
    
    site_url = current_app.config.get('SITE_URL', 'http://localhost:5000')
    
    content = f"""User-agent: *
Allow: /

Sitemap: {site_url}/sitemap.xml
"""
    
    return Response(content, mimetype='text/plain')
