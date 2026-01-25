"""
Admin Blueprint - Administrative Routes

This blueprint handles administrative functionality including:
- Admin dashboard
- House plan management (CRUD)
- Category management
- Order management
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_file, abort, session, jsonify
from flask_login import login_required, current_user, login_user, logout_user
from functools import wraps
import os
import traceback
from app.models import HousePlan, Category, Order, User, ContactMessage, Visitor, house_plan_categories
from app.forms import HousePlanForm, CategoryForm, LoginForm, MessageStatusForm, StaffCreateForm
from app.forms import PlanFAQForm
from app.extensions import db
from datetime import datetime, date, timedelta
from sqlalchemy import or_, func, inspect
from sqlalchemy.exc import SQLAlchemyError
from slugify import slugify
from urllib.parse import urlparse
from app.utils.uploads import save_uploaded_file, resolve_protected_upload
from app.domain.plan_policy import diagnose_plan, diagnostics_to_flash_messages
from app.services.admin_inbox_cache import (
    get_inbox_counts_cached,
    invalidate_inbox_counts_cache,
    refresh_inbox_counts_async,
)
from app.services.admin_inbox_service import (
    InboxFilters,
    build_messages_query,
    is_important_message,
    message_preview_text,
    toggle_important,
)
from sqlalchemy.exc import OperationalError, IntegrityError
from app.utils.media import is_absolute_url
from app.utils.pack_visibility import load_pack_visibility, save_pack_visibility
from app.models import PlanFAQ
from werkzeug.security import generate_password_hash
from app.utils.db_resilience import with_db_resilience, safe_db_query

# Create Blueprint
admin_bp = Blueprint('admin', __name__)


def _generate_unique_category_slug(name: str, *, exclude_category_id: int | None = None) -> str:
    """Generate a unique Category.slug.

    Slug collisions can happen even when Category.name is unique (punctuation,
    transliteration, etc.). We keep app-level slug uniqueness by suffixing.
    """

    base = slugify(name) or 'category'
    candidate = base
    suffix = 2

    while True:
        query = Category.query.filter(Category.slug == candidate)
        if exclude_category_id is not None:
            query = query.filter(Category.id != exclude_category_id)
        exists = query.first() is not None
        if not exists:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


def ensure_admin_exists():
    """Return the current admin user if one exists.

    Production-safe behavior: do NOT create/update admin accounts automatically.
    Use explicit CLI commands (e.g., `flask reset-admin-password`) during deploy.
    """

    try:
        return User.query.filter_by(role='superadmin').first()
    except (OperationalError, IntegrityError) as exc:
        current_app.logger.error('Database error when checking for existing admin: %s', exc)
        db.session.rollback()
        return None
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error('Admin lookup failed: %s', exc)
        return None
 
def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'superadmin':
            flash('Administrator login required.', 'warning')
            return redirect(url_for('admin.admin_login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def team_required(f):
    """Decorator to allow owner (superadmin) and staff (assistant) access."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in {'superadmin', 'staff'}:
            flash('Administrator login required.', 'warning')
            return redirect(url_for('admin.admin_login', next=request.url))
        return f(*args, **kwargs)

    return decorated_function


@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    """Private administrator login endpoint."""

    form = LoginForm()

    # Ensure an admin account exists before processing authentication.
    bootstrap_admin = ensure_admin_exists()
    if bootstrap_admin is None:
        # In production we should not block the login page when an admin account
        # is not yet present. Log a non-blocking warning so operators can act
        # (run `flask create-admin` or apply provisioning via CI), but allow the
        # login page to render. This prevents confusing UX while keeping
        # auto-seeding disabled for safety.
        current_app.logger.warning('No admin account detected during login attempt; admin provisioning required.')
        # continue to render login form; credential validation will behave normally

    # If a logged-in user is not an allowed admin role, force logout to enforce policy.
    if current_user.is_authenticated and current_user.role not in {'superadmin', 'staff'}:
        logout_user()
        flash('Admin access only. Please contact support if you need credentials.', 'warning')

    if current_user.is_authenticated and current_user.role == 'superadmin':
        return redirect(url_for('admin.dashboard'))
    if current_user.is_authenticated and current_user.role == 'staff':
        return redirect(url_for('admin.plans'))

    if form.validate_on_submit():
        username = (form.username.data or '').strip()
        
        # Use resilient database query with automatic retry
        @with_db_resilience(max_retries=2, backoff_ms=100)
        def find_admin_user():
            return User.query.filter(
                or_(User.username == username, User.email == username)
            ).first()
        
        try:
            user = find_admin_user()
        except Exception as exc:
            current_app.logger.error('Admin login query failed permanently: %s', exc, exc_info=True)
            flash('Database temporarily unavailable. Please try again shortly.', 'danger')
            return render_template('admin/login.html', form=form)

        if not user or user.role not in {'superadmin', 'staff'} or not user.check_password(form.password.data):
            flash('Invalid credentials.', 'danger')
            return render_template('admin/login.html', form=form)

        if not user.is_active:
            flash('This administrator account is disabled. Contact support.', 'danger')
            return render_template('admin/login.html', form=form)

        try:
            login_user(user, remember=True)
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session.permanent = True
            user.last_login = datetime.utcnow()
            db.session.commit()

        except Exception as exc:
            current_app.logger.exception('Failed to persist admin login for %s: %s', user.username, exc)
            db.session.rollback()
            flash('We could not complete the login. Please try again.', 'danger')
            return render_template('admin/login.html', form=form)

        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc:
            next_page = url_for('admin.dashboard') if user.role == 'superadmin' else url_for('admin.plans')
        flash(f'Welcome back, {user.username}.', 'success')
        return redirect(next_page)
    # Render the login form for GET or non-submitting requests
    return render_template('admin/login.html', form=form)


@admin_bp.route('/plans/<int:plan_id>/faqs')
@login_required
@admin_required
def manage_plan_faqs(plan_id):
    """Manage FAQs for a specific plan"""
    plan = HousePlan.query.get_or_404(plan_id)
    faqs = PlanFAQ.query.filter_by(plan_id=plan.id).order_by(PlanFAQ.id.asc()).all()
    return render_template('admin/faqs_list.html', plan=plan, faqs=faqs)


@admin_bp.route('/plans/<int:plan_id>/faqs/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_plan_faq(plan_id):
    plan = HousePlan.query.get_or_404(plan_id)
    form = PlanFAQForm()
    if form.validate_on_submit():
        try:
            faq = PlanFAQ(
                plan_id=plan.id,
                reference_code=plan.reference_code,
                question=form.question.data.strip(),
                answer=form.answer.data.strip(),
                pack_context=(form.pack_context.data or '').strip() or None,
            )
            db.session.add(faq)
            db.session.commit()
            flash('FAQ added successfully.', 'success')
            return redirect(url_for('admin.manage_plan_faqs', plan_id=plan.id))
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception('Failed to add FAQ for plan %s: %s', plan.id, exc)
            flash('Unable to save FAQ. Please try again.', 'danger')
    return render_template('admin/faqs_form.html', form=form, plan=plan)


@admin_bp.route('/faqs/<int:faq_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_plan_faq(faq_id):
    faq = PlanFAQ.query.get_or_404(faq_id)
    plan = faq.plan
    form = PlanFAQForm(obj=faq)
    if form.validate_on_submit():
        try:
            faq.question = form.question.data.strip()
            faq.answer = form.answer.data.strip()
            faq.pack_context = (form.pack_context.data or '').strip() or None
            db.session.commit()
            flash('FAQ updated successfully.', 'success')
            return redirect(url_for('admin.manage_plan_faqs', plan_id=plan.id))
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception('Failed to update FAQ %s: %s', faq_id, exc)
            flash('Unable to update FAQ. Please try again.', 'danger')
    return render_template('admin/faqs_form.html', form=form, plan=plan, faq=faq)


@admin_bp.route('/faqs/<int:faq_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_plan_faq(faq_id):
    faq = PlanFAQ.query.get_or_404(faq_id)
    plan_id = faq.plan_id
    try:
        db.session.delete(faq)
        db.session.commit()
        flash('FAQ deleted.', 'info')
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Failed to delete FAQ %s: %s', faq_id, exc)
        flash('Unable to delete FAQ. Please try again.', 'danger')
    return redirect(url_for('admin.manage_plan_faqs', plan_id=plan_id))

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """Admin dashboard with statistics"""

    try:
        # Get statistics
        total_plans = HousePlan.query.count()
        published_plans = HousePlan.query.filter_by(is_published=True).count()
        total_orders = Order.query.count()
        completed_orders = Order.query.filter_by(status='completed').count()
        total_users = User.query.count()
        total_categories = Category.query.count()
        free_plans = HousePlan.query.filter(HousePlan.free_pdf_file.isnot(None)).count()
        paid_plans = HousePlan.query.filter(
            or_(HousePlan.gumroad_pack_2_url.isnot(None), HousePlan.gumroad_pack_3_url.isnot(None))
        ).count()

        # Blog (non-fatal): if blog_posts table is missing, do not crash the dashboard.
        blog_posts_total = 0
        blog_posts_published = 0
        try:
            from app.models import BlogPost

            blog_posts_total = BlogPost.query.count()
            blog_posts_published = BlogPost.query.filter_by(status=BlogPost.STATUS_PUBLISHED).count()
        except Exception as exc:
            # Important on Postgres: clear aborted transactions caused by UndefinedTable.
            try:
                db.session.rollback()
            except Exception:
                pass
            current_app.logger.warning('Blog dashboard stats unavailable: %s', exc)

        # Recent orders
        recent_orders = Order.query.order_by(Order.created_at.desc()).limit(10).all()

        # Popular plans
        popular_plans = HousePlan.query.order_by(HousePlan.views_count.desc()).limit(5).all()
        plan_table = HousePlan.query.order_by(HousePlan.created_at.desc()).all()
        open_statuses = [ContactMessage.STATUS_NEW, ContactMessage.STATUS_IN_PROGRESS]
        inbox_counts = {
            'total': ContactMessage.query.count(),
            'new': ContactMessage.query.filter_by(status=ContactMessage.STATUS_NEW).count(),
            'open': ContactMessage.query.filter(ContactMessage.status.in_(open_statuses)).count(),
            'responded': ContactMessage.query.filter_by(status=ContactMessage.STATUS_RESPONDED).count(),
        }
        recent_messages = ContactMessage.query.order_by(ContactMessage.created_at.desc()).limit(5).all()

        stats = {
            'total_plans': total_plans,
            'published_plans': published_plans,
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'total_users': total_users,
            'total_categories': total_categories,
            'free_plans': free_plans,
            'paid_plans': paid_plans,
            'messages_total': inbox_counts['total'],
            'messages_open': inbox_counts['open'],
            'messages_new': inbox_counts['new'],
            'blog_posts_total': blog_posts_total,
            'blog_posts_published': blog_posts_published,
        }

        status_labels = dict(ContactMessage.STATUS_CHOICES)

        pack_visibility = load_pack_visibility()
        return render_template(
            'admin/dashboard.html',
            stats=stats,
            recent_orders=recent_orders,
            popular_plans=popular_plans,
            plan_table=plan_table,
            recent_messages=recent_messages,
            inbox_counts=inbox_counts,
            pack_visibility=pack_visibility,
            inquiry_labels=INQUIRY_LABELS,
            status_labels=status_labels,
        )
    except Exception as e:
        current_app.logger.error('Admin dashboard query failed: %s', e, exc_info=True)
        underlying = getattr(e, 'orig', None) or getattr(e, '__cause__', None) or e
        detail = str(underlying)
        if len(detail) > 300:
            detail = detail[:300] + '…'
        flash(f'Dashboard query failed (SQL error): {detail}', 'warning')
        pack_visibility = load_pack_visibility()
        return render_template('admin/dashboard.html',
                             stats={'total_plans': 0, 'published_plans': 0, 'total_orders': 0,
                                   'completed_orders': 0, 'total_users': 0, 'total_categories': 0,
                                   'free_plans': 0, 'paid_plans': 0, 'messages_total': 0,
                                   'messages_open': 0, 'messages_new': 0},
                             recent_orders=[],
                             popular_plans=[],
                             plan_table=[],
                             recent_messages=[],
                             inbox_counts={'total': 0, 'new': 0, 'open': 0, 'responded': 0},
                             pack_visibility=pack_visibility,
                             inquiry_labels=INQUIRY_LABELS,
                             status_labels={})


@admin_bp.route('/dashboard/pack-visibility', methods=['POST'])
@login_required
@admin_required
def update_pack_visibility():
    visibility = {
        1: bool(request.form.get('pack_1')),
        2: bool(request.form.get('pack_2')),
        3: bool(request.form.get('pack_3')),
    }
    try:
        save_pack_visibility(visibility)
        flash('Pack visibility updated.', 'success')
    except Exception as exc:
        current_app.logger.error('Failed to save pack visibility: %s', exc, exc_info=True)
        flash('Unable to update pack visibility right now.', 'danger')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/team', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_team():
    """Owner-only team management page."""

    form = StaffCreateForm()

    try:
        staff_users = (
            User.query
            .filter(User.role == 'staff')
            .order_by(User.created_at.desc(), User.id.desc())
            .all()
        )
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Failed to load staff users: %s', exc)
        staff_users = []
        flash('Unable to load team list. Please try again.', 'danger')

    if form.validate_on_submit():
        username = (form.username.data or '').strip()
        email = (form.email.data or '').strip().lower()

        try:
            staff = User(username=username, email=email, role='staff', is_active=True)
            staff.set_password(form.password.data)
            db.session.add(staff)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash('Username or email already exists.', 'danger')
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception('Failed to create staff user %s: %s', username, exc)
            flash('Unable to create staff account. Please try again.', 'danger')
        else:
            flash(f'Staff account "{staff.username}" created.', 'success')
            return redirect(url_for('admin.manage_team'))

    return render_template('admin/manage_team.html', staff_users=staff_users, form=form)


@admin_bp.route('/team/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_staff(user_id):
    """Owner-only: delete a staff account."""

    staff = db.session.get(User, user_id)
    if not staff or staff.role != 'staff':
        flash('Staff user not found.', 'warning')
        return redirect(url_for('admin.manage_team'))

    try:
        # Keep plans in place but detach author reference.
        try:
            HousePlan.query.filter_by(created_by_id=staff.id).update({'created_by_id': None})
        except Exception as detach_exc:
            db.session.rollback()
            current_app.logger.warning('Unable to detach plans for staff user %s: %s', staff.id, detach_exc)
        db.session.delete(staff)
        db.session.commit()
        flash('Staff account deleted.', 'success')
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Failed to delete staff user %s: %s', user_id, exc)
        flash('Unable to delete staff account. Please try again.', 'danger')

    return redirect(url_for('admin.manage_team'))


@admin_bp.route('/visitors')
@login_required
@admin_required
def visitors():
    """Legacy visitors dashboard (deprecated).

    Consolidated into the smart analytics dashboard.
    """

    flash('Visitor tracking is now available in Smart Analytics.', 'info')
    return redirect(url_for('admin.analytics'))


@admin_bp.route('/analytics')
@login_required
@admin_required
def analytics():
    """Smart analytics dashboard (aggregated + bounded retention)."""

    from app.services.analytics.dashboard import build_dashboard_payload
    from app.services.analytics.maintenance import clean_old_logs

    skip_cleanup = (request.args.get('skip_cleanup') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
    cleanup_ran = False
    cleanup_error = None

    if not skip_cleanup:
        try:
            retention_days = int(current_app.config.get('ANALYTICS_RETENTION_DAYS', 7) or 7)
            clean_old_logs(retention_days=retention_days)
            cleanup_ran = True
        except Exception as exc:
            try:
                db.session.rollback()
            except Exception:
                pass
            cleanup_error = str(exc)
            current_app.logger.warning('Smart analytics cleanup failed: %s', exc)

    retention_days = int(current_app.config.get('ANALYTICS_RETENTION_DAYS', 7) or 7)
    retention_days = max(1, min(retention_days, 60))

    try:
        payload = build_dashboard_payload(days=min(7, retention_days))
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        current_app.logger.exception('Failed to build smart analytics dashboard: %s', exc)
        flash('Unable to load smart analytics right now. Please try again.', 'warning')
        payload = {'window_days': min(7, retention_days), 'series': [], 'totals': {}, 'top_countries': []}

    # Visitor explorer (RecentLog): filterable table for the last N days (bounded).
    from app.models import RecentLog

    explore_page = request.args.get('page', 1, type=int)
    explore_per_page = request.args.get('per_page', 50, type=int)
    explore_per_page = max(10, min(explore_per_page, 100))

    explore_days = request.args.get('days', min(7, retention_days), type=int)
    explore_days = max(1, min(explore_days, retention_days))

    explore_type = (request.args.get('type') or 'human').strip().lower()
    if explore_type not in {'human', 'bot', 'crawler', 'all'}:
        explore_type = 'human'

    explore_q = (request.args.get('q') or '').strip()
    explore_country = (request.args.get('country') or '').strip()

    now = datetime.utcnow()
    since = now - timedelta(days=explore_days)

    explore_total = 0
    explore_unique_ips = 0
    explore_sessions = 0
    explore_top_pages = []
    explore_top_countries = []
    explore_pagination = None

    try:
        inspector = inspect(db.engine)
        has_recent_logs = inspector.has_table('recent_logs')
    except Exception as exc:
        has_recent_logs = False
        current_app.logger.warning('RecentLog table check failed: %s', exc)

    if has_recent_logs:
        try:
            explore_query = RecentLog.query.filter(RecentLog.timestamp >= since)
            if explore_type == 'crawler':
                explore_query = explore_query.filter(RecentLog.traffic_type == 'bot').filter(RecentLog.is_search_bot.is_(True))
            elif explore_type != 'all':
                explore_query = explore_query.filter(RecentLog.traffic_type == explore_type)

            if explore_country:
                like_country = f"%{explore_country}%"
                explore_query = explore_query.filter(
                    or_(
                        RecentLog.country_code.ilike(like_country),
                        RecentLog.country_name.ilike(like_country),
                    )
                )

            if explore_q:
                like_pattern = f"%{explore_q}%"
                explore_query = explore_query.filter(
                    or_(
                        RecentLog.ip_address.ilike(like_pattern),
                        RecentLog.request_path.ilike(like_pattern),
                        RecentLog.user_agent.ilike(like_pattern),
                        RecentLog.referrer.ilike(like_pattern),
                        RecentLog.country_name.ilike(like_pattern),
                        RecentLog.country_code.ilike(like_pattern),
                        RecentLog.session_id.ilike(like_pattern),
                    )
                )

            explore_query_unordered = explore_query.order_by(None)
            explore_pagination = (
                explore_query
                .order_by(RecentLog.timestamp.desc())
                .paginate(page=explore_page, per_page=explore_per_page, error_out=False)
            )

            explore_total = explore_query_unordered.with_entities(func.count(RecentLog.id)).scalar() or 0
            explore_unique_ips = explore_query_unordered.with_entities(func.count(func.distinct(RecentLog.ip_address))).scalar() or 0
            explore_sessions = explore_query_unordered.with_entities(func.count(func.distinct(RecentLog.session_id))).scalar() or 0

            explore_top_pages = (
                explore_query_unordered
                .with_entities(RecentLog.request_path, func.count(RecentLog.id))
                .group_by(RecentLog.request_path)
                .order_by(func.count(RecentLog.id).desc())
                .limit(8)
                .all()
            )

            explore_top_countries = (
                explore_query_unordered
                .with_entities(RecentLog.country_name, RecentLog.country_code, func.count(RecentLog.id))
                .group_by(RecentLog.country_name, RecentLog.country_code)
                .order_by(func.count(RecentLog.id).desc())
                .limit(8)
                .all()
            )
        except SQLAlchemyError as exc:
            try:
                db.session.rollback()
            except Exception:
                pass
            current_app.logger.exception('RecentLog explorer query failed: %s', exc)
            explore_pagination = None

    if explore_pagination is None:
        from types import SimpleNamespace

        explore_pagination = SimpleNamespace(
            items=[],
            page=1,
            pages=0,
            per_page=explore_per_page,
            total=0,
            has_prev=False,
            has_next=False,
            prev_num=None,
            next_num=None,
        )

    query_args = request.args.to_dict(flat=True)
    query_args.pop('page', None)

    return render_template(
        'admin/analytics.html',
        payload=payload,
        cleanup_ran=cleanup_ran,
        cleanup_error=cleanup_error,
        visits=explore_pagination.items,
        visits_pagination=explore_pagination,
        visits_stats={
            'days': explore_days,
            'type': explore_type,
            'q': explore_q,
            'country': explore_country,
            'total': int(explore_total),
            'unique_ips': int(explore_unique_ips),
            'sessions': int(explore_sessions),
            'per_page': explore_per_page,
        },
        visits_top_pages=explore_top_pages,
        visits_top_countries=explore_top_countries,
        query_args=query_args,
    )


@admin_bp.route('/analytics/live')
@login_required
@admin_required
def analytics_live():
    """Live recent visits (JSON) for the admin analytics page.

    Returns recent `RecentLog` rows, suitable for polling every minute.
    """

    from app.models import RecentLog

    limit = request.args.get('limit', 50, type=int)
    limit = max(10, min(limit, 200))

    minutes = request.args.get('minutes', 60, type=int)
    retention_days = int(current_app.config.get('ANALYTICS_RETENTION_DAYS', 7) or 7)
    retention_minutes = max(60, min(int(retention_days) * 24 * 60, 60 * 24 * 60))
    minutes = max(1, min(minutes, retention_minutes))

    traffic_type = (request.args.get('type') or 'human').strip().lower()
    if traffic_type not in {'human', 'bot', 'attack', 'all', 'crawler'}:
        traffic_type = 'human'

    now = datetime.utcnow()
    since = now - timedelta(minutes=minutes)

    query = RecentLog.query.filter(RecentLog.timestamp >= since)
    if traffic_type == 'crawler':
        query = query.filter(RecentLog.traffic_type == 'bot').filter(RecentLog.is_search_bot.is_(True))
    elif traffic_type != 'all':
        query = query.filter(RecentLog.traffic_type == traffic_type)

    rows = (
        query
        .order_by(RecentLog.timestamp.desc())
        .limit(limit)
        .all()
    )

    last_minute_since = now - timedelta(minutes=1)
    last_minute_query = RecentLog.query.filter(RecentLog.timestamp >= last_minute_since)
    if traffic_type == 'crawler':
        last_minute_query = last_minute_query.filter(RecentLog.traffic_type == 'bot').filter(RecentLog.is_search_bot.is_(True))
    elif traffic_type != 'all':
        last_minute_query = last_minute_query.filter(RecentLog.traffic_type == traffic_type)

    last_minute_count = last_minute_query.with_entities(func.count(RecentLog.id)).scalar() or 0
    last_minute_unique_ips = (
        last_minute_query.with_entities(func.count(func.distinct(RecentLog.ip_address))).scalar()
        or 0
    )
    last_minute_sessions = (
        last_minute_query.with_entities(func.count(func.distinct(RecentLog.session_id))).scalar()
        or 0
    )

    return jsonify(
        {
            'now_utc': now.isoformat(),
            'since_minutes': minutes,
            'limit': limit,
            'traffic_type': traffic_type,
            'stats': {
                'events_last_minute': int(last_minute_count),
                'unique_ips_last_minute': int(last_minute_unique_ips),
                'active_sessions_last_minute': int(last_minute_sessions),
            },
            'rows': [
                {
                    'timestamp': (r.timestamp.isoformat() if r.timestamp else None),
                    'ip': r.ip_address,
                    'country_code': r.country_code,
                    'country_name': r.country_name,
                    'path': r.request_path,
                    'type': ('crawler' if (r.traffic_type == 'bot' and getattr(r, 'is_search_bot', False)) else r.traffic_type),
                    'method': r.method,
                    'status_code': r.status_code,
                    'response_time_ms': r.response_time_ms,
                    'user_agent': r.user_agent,
                    'device': r.device,
                    'referrer': r.referrer,
                    'session_id': r.session_id,
                }
                for r in rows
            ],
        }
    )


@admin_bp.route('/analytics/export')
@login_required
@admin_required
def analytics_export():
    """Export recent traffic logs as CSV (respects current explorer filters)."""

    import csv
    import io
    from flask import Response
    from app.models import RecentLog

    retention_days = int(current_app.config.get('ANALYTICS_RETENTION_DAYS', 7) or 7)
    retention_days = max(1, min(retention_days, 60))

    explore_days = request.args.get('days', min(7, retention_days), type=int)
    explore_days = max(1, min(explore_days, retention_days))

    explore_type = (request.args.get('type') or 'human').strip().lower()
    if explore_type not in {'human', 'bot', 'crawler', 'all'}:
        explore_type = 'human'

    explore_q = (request.args.get('q') or '').strip()
    explore_country = (request.args.get('country') or '').strip()

    since = datetime.utcnow() - timedelta(days=explore_days)
    query = RecentLog.query.filter(RecentLog.timestamp >= since)
    if explore_type == 'crawler':
        query = query.filter(RecentLog.traffic_type == 'bot').filter(RecentLog.is_search_bot.is_(True))
    elif explore_type != 'all':
        query = query.filter(RecentLog.traffic_type == explore_type)

    if explore_country:
        like_country = f"%{explore_country}%"
        query = query.filter(or_(RecentLog.country_code.ilike(like_country), RecentLog.country_name.ilike(like_country)))

    if explore_q:
        like_pattern = f"%{explore_q}%"
        query = query.filter(
            or_(
                RecentLog.ip_address.ilike(like_pattern),
                RecentLog.request_path.ilike(like_pattern),
                RecentLog.user_agent.ilike(like_pattern),
                RecentLog.referrer.ilike(like_pattern),
                RecentLog.country_name.ilike(like_pattern),
                RecentLog.country_code.ilike(like_pattern),
                RecentLog.session_id.ilike(like_pattern),
            )
        )

    limit = request.args.get('limit', 5000, type=int)
    limit = max(100, min(limit, 20000))

    rows = (
        query
        .order_by(RecentLog.timestamp.desc())
        .limit(limit)
        .all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            'timestamp_utc',
            'traffic_type',
            'is_search_bot',
            'ip_address',
            'country_code',
            'country_name',
            'request_path',
            'method',
            'status_code',
            'response_time_ms',
            'device',
            'referrer',
            'session_id',
            'user_agent',
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r.timestamp.isoformat() if r.timestamp else '',
                r.traffic_type or '',
                '1' if getattr(r, 'is_search_bot', False) else '0',
                r.ip_address or '',
                r.country_code or '',
                r.country_name or '',
                r.request_path or '',
                r.method or '',
                str(r.status_code) if r.status_code is not None else '',
                str(r.response_time_ms) if r.response_time_ms is not None else '',
                r.device or '',
                r.referrer or '',
                r.session_id or '',
                r.user_agent or '',
            ]
        )

    filename = f"traffic_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        buffer.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


@admin_bp.route('/visitors/export')
@login_required
@admin_required
def visitors_export():
    """Legacy export endpoint (deprecated).

    Redirects to the unified analytics export.
    """

    return redirect(url_for('admin.analytics_export', **request.args.to_dict(flat=True)))


@admin_bp.route('/')
@login_required
@admin_required
def admin_index():
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/plans')
@login_required
@team_required
def plans():
    """List all house plans"""

    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        per_page = max(10, min(per_page, 100))

        query = HousePlan.query

        # Staff visibility: can see their own plans + all drafts.
        if current_user.role == 'staff':
            query = query.filter(
                or_(
                    HousePlan.created_by_id == current_user.id,
                    HousePlan.is_published.is_(False),
                )
            )

        search = request.args.get('q', '').strip()
        if search:
            like_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    HousePlan.title.ilike(like_pattern),
                    HousePlan.reference_code.ilike(like_pattern),
                    HousePlan.slug.ilike(like_pattern),
                )
            )

        status = request.args.get('status')
        if status == 'published':
            query = query.filter(HousePlan.is_published.is_(True))
        elif status == 'draft':
            query = query.filter(HousePlan.is_published.is_(False))

        category_id = request.args.get('category', type=int)
        if category_id:
            query = (
                query.join(HousePlan.categories)
                .filter(Category.id == category_id)
                .distinct()
            )

        pack_filter = request.args.get('pack')
        if pack_filter == 'free':
            query = query.filter(HousePlan.free_pdf_file.isnot(None))
        elif pack_filter == 'paid':
            query = query.filter(
                or_(HousePlan.gumroad_pack_2_url.isnot(None), HousePlan.gumroad_pack_3_url.isnot(None))
            )

        sort = request.args.get('sort', 'newest')
        if sort == 'updated':
            query = query.order_by(HousePlan.updated_at.desc(), HousePlan.id.desc())
        elif sort == 'title':
            query = query.order_by(HousePlan.title.asc())
        elif sort == 'views':
            query = query.order_by(HousePlan.views_count.desc())
        elif sort == 'price_low':
            query = query.order_by(HousePlan.price.asc())
        else:
            query = query.order_by(HousePlan.created_at.desc())

        plans = query.paginate(page=page, per_page=per_page, error_out=False)

        filters = {
            'search': search,
            'status': status or '',
            'category': category_id or '',
            'pack': pack_filter or '',
            'sort': sort,
            'per_page': per_page,
        }

        categories = Category.query.order_by(Category.name.asc()).all()
        stats_query = HousePlan.query
        if current_user.role == 'staff':
            stats_query = stats_query.filter(
                or_(
                    HousePlan.created_by_id == current_user.id,
                    HousePlan.is_published.is_(False),
                )
            )
        stats = {
            'total': stats_query.count(),
            'published': stats_query.filter_by(is_published=True).count(),
            'draft': stats_query.filter_by(is_published=False).count(),
            'free': stats_query.filter(HousePlan.free_pdf_file.isnot(None)).count(),
        }

        query_args = request.args.to_dict(flat=True)
        query_args.pop('page', None)

        return render_template(
            'admin/plans_list.html',
            plans=plans,
            filters=filters,
            categories=categories,
            stats=stats,
            query_args=query_args,
        )

    except Exception as exc:
        db.session.rollback()
        print(traceback.format_exc())
        current_app.logger.error('Failed to load plans list: %s', exc, exc_info=True)
        flash('Unable to load plans right now. Please try again later.', 'danger')
        return redirect(url_for('admin.dashboard'))


OPEN_INBOX_STATUSES = (
    ContactMessage.STATUS_NEW,
    ContactMessage.STATUS_IN_PROGRESS,
)

INQUIRY_LABELS = {
    'plans': 'Plan selection & availability',
    'orders': 'Gumroad orders & downloads',
    'custom': 'Custom project or collaboration',
    'support': 'Technical support',
}


@admin_bp.route('/messages')
@login_required
@admin_required
def messages():
    """List stored contact messages for follow-up."""

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = max(10, min(per_page, 100))

    filters = InboxFilters(
        status=request.args.get('status', 'open'),
        inquiry_type=request.args.get('type', ''),
        q=request.args.get('q', '').strip(),
        sender=request.args.get('sender', '').strip(),
        subject=request.args.get('subject', '').strip(),
        date_from=request.args.get('from', '').strip(),
        date_to=request.args.get('to', '').strip(),
        important=request.args.get('important', '').strip(),
        include_body=request.args.get('body', '').strip(),
        sort=request.args.get('sort', 'date_desc').strip(),
        per_page=per_page,
    )

    refresh_inbox_counts_async()

    query = build_messages_query(filters)
    messages_page = query.paginate(page=page, per_page=per_page, error_out=False)

    status_counts = get_inbox_counts_cached()

    status_options = [
        ('open', 'Open'),
        ('all', 'All'),
    ] + list(ContactMessage.STATUS_CHOICES)

    inquiry_options = [('', 'All topics')] + [(key, label) for key, label in INQUIRY_LABELS.items()]

    filters_dict = {
        'status': filters.status,
        'type': filters.inquiry_type,
        'q': filters.q,
        'sender': filters.sender,
        'subject': filters.subject,
        'from': filters.date_from,
        'to': filters.date_to,
        'important': filters.important,
        'body': filters.include_body,
        'sort': filters.sort,
        'per_page': per_page,
    }

    query_args = request.args.to_dict(flat=True)
    query_args.pop('page', None)

    status_labels = dict(ContactMessage.STATUS_CHOICES)

    return render_template(
        'admin/messages_list.html',
        messages=messages_page.items,
        pagination=messages_page,
        filters=filters_dict,
        status_counts=status_counts,
        status_options=status_options,
        inquiry_options=inquiry_options,
        inquiry_labels=INQUIRY_LABELS,
        query_args=query_args,
        status_labels=status_labels,
        important_tag='[IMPORTANT]',
        important_predicate=is_important_message,
    )


@admin_bp.route('/messages/fragment')
@login_required
@admin_required
def messages_fragment():
    """Fast partial rendering for instant search/filter UX."""

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = max(10, min(per_page, 100))

    filters = InboxFilters(
        status=request.args.get('status', 'open'),
        inquiry_type=request.args.get('type', ''),
        q=request.args.get('q', '').strip(),
        sender=request.args.get('sender', '').strip(),
        subject=request.args.get('subject', '').strip(),
        date_from=request.args.get('from', '').strip(),
        date_to=request.args.get('to', '').strip(),
        important=request.args.get('important', '').strip(),
        include_body=request.args.get('body', '').strip(),
        sort=request.args.get('sort', 'date_desc').strip(),
        per_page=per_page,
    )

    query = build_messages_query(filters)
    messages_page = query.paginate(page=page, per_page=per_page, error_out=False)

    query_args = request.args.to_dict(flat=True)
    query_args.pop('page', None)
    status_labels = dict(ContactMessage.STATUS_CHOICES)

    html = render_template(
        'admin/_messages_fragment.html',
        messages=messages_page.items,
        pagination=messages_page,
        query_args=query_args,
        inquiry_labels=INQUIRY_LABELS,
        status_labels=status_labels,
        important_predicate=is_important_message,
    )

    resp = current_app.response_class(html)
    resp.headers['X-Total'] = str(messages_page.total)
    resp.headers['X-Page'] = str(messages_page.page)
    resp.headers['X-Pages'] = str(messages_page.pages or 1)
    return resp


@admin_bp.route('/messages/preview/<int:message_id>')
@login_required
@admin_required
def message_preview(message_id: int):
    """Return a lightweight preview for quick-open without loading full detail UI."""

    msg = ContactMessage.query.get_or_404(message_id)
    return jsonify({
        'id': msg.id,
        'preview': message_preview_text(msg.message),
    })


@admin_bp.route('/messages/bulk', methods=['POST'])
@login_required
@admin_required
def messages_bulk_action():
    """Bulk operations for high-volume inbox workflows."""

    payload = request.get_json(silent=True) or {}
    action = (payload.get('action') or '').strip()
    ids = payload.get('ids') or []

    try:
        ids_int = sorted({int(x) for x in ids})
    except Exception:
        return jsonify({'ok': False, 'error': 'Invalid ids'}), 400
    if not ids_int:
        return jsonify({'ok': False, 'error': 'No messages selected'}), 400

    messages = ContactMessage.query.filter(ContactMessage.id.in_(ids_int)).all()
    if not messages:
        return jsonify({'ok': False, 'error': 'No messages found'}), 404

    changed = 0
    deleted = 0

    try:
        if action in {'new', 'in_progress', 'responded', 'archived'}:
            for m in messages:
                before = m.status
                m.mark_status(action)
                if m.status != before:
                    changed += 1

        elif action == 'important_on':
            for m in messages:
                before = m.admin_notes or ''
                m.admin_notes = toggle_important(before, True)
                if (m.admin_notes or '') != before:
                    changed += 1

        elif action == 'important_off':
            for m in messages:
                before = m.admin_notes or ''
                m.admin_notes = toggle_important(before, False)
                if (m.admin_notes or '') != before:
                    changed += 1

        elif action == 'delete':
            for m in messages:
                db.session.delete(m)
                deleted += 1
        else:
            return jsonify({'ok': False, 'error': 'Unknown action'}), 400

        db.session.commit()
        invalidate_inbox_counts_cache()
        return jsonify({'ok': True, 'changed': changed, 'deleted': deleted})
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Bulk inbox action failed: %s', exc)
        return jsonify({'ok': False, 'error': 'Server error'}), 500


@admin_bp.route('/messages/<int:message_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def message_detail(message_id):
    """Display a single message thread and allow status updates."""

    message = ContactMessage.query.get_or_404(message_id)
    form = MessageStatusForm(obj=message)

    if form.validate_on_submit():
        message.admin_notes = form.admin_notes.data
        message.mark_status(form.status.data)
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception('Failed to update message %s: %s', message.id, exc)
            flash('Unable to update the message. Please try again.', 'danger')
        else:
            label_map = dict(ContactMessage.STATUS_CHOICES)
            flash(f"Message marked as {label_map.get(message.status, message.status)}.", 'success')
            invalidate_inbox_counts_cache()
            return redirect(url_for('admin.message_detail', message_id=message.id))
    status_labels = dict(ContactMessage.STATUS_CHOICES)

    return render_template(
        'admin/message_detail.html',
        message=message,
        form=form,
        inquiry_labels=INQUIRY_LABELS,
        status_labels=status_labels,
    )


@admin_bp.route('/messages/<int:message_id>/attachment')
@login_required
@admin_required
def message_attachment(message_id):
    """Allow administrators to download a stored attachment."""

    message = ContactMessage.query.get_or_404(message_id)
    if not message.attachment_path:
        abort(404)

    if is_absolute_url(message.attachment_path):
        return redirect(message.attachment_path)

    try:
        absolute_path = resolve_protected_upload(message.attachment_path)
    except ValueError:
        abort(400)

    if not absolute_path.exists():
        abort(404)

    download_name = message.attachment_name or absolute_path.name
    return send_file(absolute_path, as_attachment=True, download_name=download_name)


@admin_bp.route('/plans/add', methods=['GET', 'POST'])
@login_required
@team_required
def add_plan():
    """Add new house plan"""
    
    form = HousePlanForm()

    # Clear any failed transaction state from previous errors (Postgres safety).
    try:
        db.session.rollback()
    except Exception:
        pass
    
    try:
        categories = Category.query.order_by(Category.name).all()
    except Exception as exc:
        db.session.rollback()
        print(traceback.format_exc())
        current_app.logger.error('Failed to load categories for add_plan: %s', exc, exc_info=True)
        flash('Unable to load categories. Please try again in a moment.', 'danger')
        return redirect(url_for('admin.plans'))

    if not categories:
        if current_user.role == 'staff':
            flash('No categories exist yet. Ask the Owner to create categories before adding plans.', 'warning')
            return redirect(url_for('admin.plans'))
        flash('Please create at least one category first.', 'warning')
        return redirect(url_for('admin.categories'))
    form.category_ids.choices = [(c.id, c.name) for c in categories]
    
    if request.method == 'POST':
        current_app.logger.info('Session before POST: user_id=%s, username=%s, role=%s, permanent=%s', 
                               session.get('user_id'), session.get('username'), session.get('role'), session.permanent)
    
    if form.validate_on_submit():
        is_draft_save = bool(getattr(form, 'save_draft', None) and form.save_draft.data)
        draft_title = (form.title.data or '').strip()
        if not draft_title and is_draft_save:
            draft_title = f"Draft plan {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
        draft_description = (form.description.data or '').strip()
        if not draft_description and is_draft_save:
            draft_description = 'Draft plan details pending.'
        draft_price = form.price.data if form.price.data is not None else (0 if is_draft_save else None)

        plan = HousePlan(
            title=draft_title,
            description=draft_description,
            short_description=form.short_description.data,
            plan_type=form.plan_type.data or None,
            bedrooms=form.bedrooms.data,
            bathrooms=form.bathrooms.data,
            stories=form.stories.data,
            garage=form.garage.data,
            price=draft_price,
            sale_price=form.sale_price.data,
            price_pack_1=form.price_pack_1.data if form.price_pack_1.data is not None else 0,
            price_pack_2=form.price_pack_2.data,
            price_pack_3=form.price_pack_3.data,
            is_featured=form.is_featured.data,
            is_published=form.is_published.data
        )

        # Accountability: track who created the plan.
        plan.created_by_id = current_user.id

        # Staff safety: staff cannot publish.
        if current_user.role == 'staff':
            plan.is_published = False

        try:
            selected_categories = Category.query.filter(Category.id.in_(form.category_ids.data)).all()
            plan.categories = selected_categories

            plan.total_area_m2 = form.total_area_m2.data
            plan.total_area_sqft = form.total_area_sqft.data
            plan.number_of_bedrooms = form.bedrooms.data
            plan.number_of_bathrooms = float(form.bathrooms.data) if form.bathrooms.data is not None else None
            plan.number_of_floors = form.stories.data
            plan.parking_spaces = form.garage.data
            plan.building_width = form.building_width.data
            plan.building_length = form.building_length.data
            plan.roof_type = form.roof_type.data
            plan.structure_type = form.structure_type.data
            plan.foundation_type = form.foundation_type.data
            plan.ceiling_height = form.ceiling_height.data
            plan.construction_complexity = form.construction_complexity.data or None
            plan.estimated_construction_cost_note = form.estimated_construction_cost_note.data
            plan.suitable_climate = form.suitable_climate.data
            plan.ideal_for = form.ideal_for.data
            plan.main_features = form.main_features.data
            plan.room_details = form.room_details.data
            plan.construction_notes = form.construction_notes.data

            plan.design_philosophy = form.design_philosophy.data
            plan.lifestyle_suitability = form.lifestyle_suitability.data
            plan.customization_potential = form.customization_potential.data

            if plan.total_area_sqft:
                plan.square_feet = int(plan.total_area_sqft)
            elif plan.total_area_m2:
                plan.square_feet = int(plan.total_area_m2 * 10.7639)

            plan.gumroad_pack_2_url = form.gumroad_pack_2_url.data
            plan.gumroad_pack_3_url = form.gumroad_pack_3_url.data

            cover_upload = form.cover_image.data
            if cover_upload and getattr(cover_upload, 'filename', ''):
                plan.cover_image = save_uploaded_file(cover_upload, 'plans')

            pdf_upload = form.free_pdf_file.data
            if pdf_upload and getattr(pdf_upload, 'filename', ''):
                plan.free_pdf_file = save_uploaded_file(pdf_upload, 'pdfs')

            plan.seo_title = form.seo_title.data
            plan.seo_description = form.seo_description.data
            plan.seo_keywords = form.seo_keywords.data

            diagnostics = diagnose_plan(plan)
            # Non-blocking: surface policy issues as flash messages to reduce
            # manual admin reasoning while preserving existing behavior.
            if form.is_published.data or plan.gumroad_pack_2_url or plan.gumroad_pack_3_url:
                for category, message in diagnostics_to_flash_messages(diagnostics):
                    flash(message, category)

            # If the admin clicked "Save Draft", ensure the plan remains unpublished
            if is_draft_save:
                plan.is_published = False
        except ValueError as upload_error:
            db.session.rollback()
            flash(str(upload_error), 'danger')
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception('Failed to add plan "%s": %s', form.title.data, exc)
            flash('Unable to save the plan. No data was written.', 'danger')
        else:
            try:
                db.session.add(plan)
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                current_app.logger.exception('Failed to persist new plan "%s": %s', form.title.data, exc)
                flash('Unable to save the plan. No data was written.', 'danger')
            else:
                # Provide specific feedback and redirect depending on whether this
                # was an explicit "Save Draft" action or a full publish/save.
                if is_draft_save:
                    flash(f'House plan "{plan.title}" has been saved as a draft.', 'info')
                    current_app.logger.info('Session after POST (draft save): user_id=%s, username=%s, role=%s, permanent=%s',
                                            session.get('user_id'), session.get('username'), session.get('role'), session.permanent)
                    return redirect(url_for('admin.edit_plan', id=plan.id))
                flash(f'House plan "{plan.title}" has been added successfully!', 'success')
                current_app.logger.info('Session after POST: user_id=%s, username=%s, role=%s, permanent=%s', 
                                       session.get('user_id'), session.get('username'), session.get('role'), session.permanent)
                return redirect(url_for('admin.plans'))
    
    return render_template('admin/add_plan.html', form=form)


@admin_bp.route('/plans/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@team_required
def edit_plan(id):
    """Edit existing house plan with hardened transaction guarantees."""

    class UploadProcessError(Exception):
        """Raised when a file upload fails so we can stop processing safely."""

    def _log_upload_size(field_name, storage):
        size = getattr(storage, 'content_length', None)
        if size is None:
            try:
                current_pos = storage.stream.tell()
                storage.stream.seek(0, os.SEEK_END)
                size = storage.stream.tell()
                storage.stream.seek(current_pos)
            except Exception:
                print(traceback.format_exc())
                size = 'unknown'
        filename = getattr(storage, 'filename', 'unknown')
        current_app.logger.info(
            'Admin upload incoming | plan_id=%s field=%s filename=%s size=%s bytes',
            id,
            field_name,
            filename,
            size,
        )
        print(f'UPLOAD DEBUG | plan_id={id} field={field_name} filename={filename} size={size}')

    def _save_upload(storage, folder, field_name):
        _log_upload_size(field_name, storage)
        try:
            return save_uploaded_file(storage, folder)
        except Exception as upload_exc:
            db.session.rollback()
            print(traceback.format_exc())
            current_app.logger.error(
                'Upload failed for plan id=%s field=%s: %s',
                id,
                field_name,
                upload_exc,
            )
            flash(f'{field_name.replace("_", " ").title()} upload failed. No changes were saved.', 'danger')
            raise UploadProcessError(field_name) from upload_exc

    try:
        try:
            plan = db.session.get(HousePlan, id)
        except Exception as load_exc:
            db.session.rollback()
            print(traceback.format_exc())
            current_app.logger.error('Failed to load plan id=%s for edit (DB/query error): %s', id, load_exc)
            flash('Unable to load this plan right now (database error). Please try again.', 'danger')
            return redirect(url_for('admin.plans'))

        if plan is None:
            flash('House plan not found.', 'warning')
            return redirect(url_for('admin.plans'))

        if current_user.role == 'staff' and plan.created_by_id != current_user.id:
            flash('You can only edit plans you created.', 'warning')
            return redirect(url_for('admin.plans'))

        form = HousePlanForm(obj=plan)

        try:
            categories = Category.query.order_by(Category.name).all()
        except Exception as cat_exc:
            print(traceback.format_exc())
            current_app.logger.error('Failed to load categories while editing plan id=%s: %s', id, cat_exc)
            categories = []
            flash('Categories could not be loaded (database error). You can still edit other fields.', 'warning')

        form.category_ids.choices = [(c.id, c.name) for c in categories]

        if request.method == 'GET':
            try:
                form.category_ids.data = [c.id for c in (plan.categories or [])]
            except Exception as prefill_exc:
                print(traceback.format_exc())
                current_app.logger.error('Failed to prefill category_ids for plan id=%s: %s', id, prefill_exc)
                form.category_ids.data = []

        if request.method == 'POST':
            try:
                if getattr(form.category_ids, 'raw_data', None) is None:
                    form.category_ids.data = [c.id for c in (plan.categories or [])]
            except Exception as preserve_exc:
                print(traceback.format_exc())
                current_app.logger.error('Failed to preserve category_ids on POST for plan id=%s: %s', id, preserve_exc)

        if form.validate_on_submit():
            is_draft_save = bool(getattr(form, 'save_draft', None) and form.save_draft.data)
            title_value = (form.title.data or '').strip()
            description_value = (form.description.data or '').strip()
            price_value = form.price.data
            if is_draft_save:
                if not title_value:
                    title_value = plan.title or f"Draft plan {datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
                if not description_value:
                    description_value = plan.description or 'Draft plan details pending.'
                if price_value is None:
                    price_value = plan.price if plan.price is not None else 0

            try:
                plan.title = title_value
                plan.description = description_value
                plan.short_description = form.short_description.data
                plan.plan_type = form.plan_type.data or None
                plan.bedrooms = form.bedrooms.data
                plan.bathrooms = form.bathrooms.data
                plan.stories = form.stories.data
                plan.garage = form.garage.data
                plan.price = price_value
                plan.sale_price = form.sale_price.data
                if form.price_pack_1.data is not None:
                    plan.price_pack_1 = form.price_pack_1.data
                if form.price_pack_2.data is not None:
                    plan.price_pack_2 = form.price_pack_2.data
                else:
                    plan.price_pack_2 = None
                if form.price_pack_3.data is not None:
                    plan.price_pack_3 = form.price_pack_3.data
                else:
                    plan.price_pack_3 = None
                if plan.price_pack_1 is None:
                    plan.price_pack_1 = 0

                if getattr(form.category_ids, 'raw_data', None) is not None:
                    category_ids = form.category_ids.data or []
                    if category_ids:
                        try:
                            selected_categories = Category.query.filter(Category.id.in_(category_ids)).all()
                        except Exception as selected_exc:
                            print(traceback.format_exc())
                            current_app.logger.error(
                                'Failed to load selected categories for plan id=%s; category_ids=%s; %s',
                                plan.id,
                                category_ids,
                                selected_exc,
                            )
                            selected_categories = []
                            flash('Selected categories could not be saved (database error).', 'warning')
                    else:
                        selected_categories = []
                    plan.categories = selected_categories

                plan.is_featured = form.is_featured.data
                if current_user.role == 'staff':
                    plan.is_published = False
                else:
                    plan.is_published = form.is_published.data

                plan.total_area_m2 = form.total_area_m2.data
                plan.total_area_sqft = form.total_area_sqft.data
                plan.number_of_bedrooms = form.bedrooms.data
                plan.number_of_bathrooms = float(form.bathrooms.data) if form.bathrooms.data is not None else None
                plan.number_of_floors = form.stories.data
                plan.parking_spaces = form.garage.data
                plan.building_width = form.building_width.data
                plan.building_length = form.building_length.data
                plan.roof_type = form.roof_type.data
                plan.structure_type = form.structure_type.data
                plan.foundation_type = form.foundation_type.data
                plan.ceiling_height = form.ceiling_height.data
                plan.construction_complexity = form.construction_complexity.data or None
                plan.estimated_construction_cost_note = form.estimated_construction_cost_note.data
                plan.suitable_climate = form.suitable_climate.data
                plan.ideal_for = form.ideal_for.data
                plan.main_features = form.main_features.data
                plan.room_details = form.room_details.data
                plan.construction_notes = form.construction_notes.data

                plan.design_philosophy = form.design_philosophy.data
                plan.lifestyle_suitability = form.lifestyle_suitability.data
                plan.customization_potential = form.customization_potential.data

                if plan.total_area_sqft:
                    plan.square_feet = int(plan.total_area_sqft)
                elif plan.total_area_m2:
                    plan.square_feet = int(plan.total_area_m2 * 10.7639)

                plan.gumroad_pack_2_url = form.gumroad_pack_2_url.data
                plan.gumroad_pack_3_url = form.gumroad_pack_3_url.data

                cover_upload = form.cover_image.data
                if cover_upload and getattr(cover_upload, 'filename', ''):
                    plan.cover_image = _save_upload(cover_upload, 'plans', 'cover_image')

                pdf_upload = form.free_pdf_file.data
                if pdf_upload and getattr(pdf_upload, 'filename', ''):
                    plan.free_pdf_file = _save_upload(pdf_upload, 'pdfs', 'free_pdf_file')

                plan.seo_title = form.seo_title.data
                plan.seo_description = form.seo_description.data
                plan.seo_keywords = form.seo_keywords.data

                diagnostics = diagnose_plan(plan)
                if form.is_published.data or plan.gumroad_pack_2_url or plan.gumroad_pack_3_url:
                    for category, message in diagnostics_to_flash_messages(diagnostics):
                        flash(message, category)

                plan.updated_at = datetime.utcnow()

                if getattr(form, 'save_draft', None) and form.save_draft.data:
                    plan.is_published = False

                plan = db.session.merge(plan)
                db.session.commit()
            except UploadProcessError:
                print(traceback.format_exc())
                return render_template('admin/edit_plan.html', form=form, plan=plan)
            except ValueError as upload_error:
                db.session.rollback()
                print(traceback.format_exc())
                flash(str(upload_error), 'danger')
            except Exception as exc:
                db.session.rollback()
                print(traceback.format_exc())
                current_app.logger.error('Failed to update plan %s: %s', plan.id, exc)
                flash('Unable to update the plan. Your changes were not saved.', 'danger')
            else:
                if getattr(form, 'save_draft', None) and form.save_draft.data:
                    flash(f'House plan "{plan.title}" has been saved as a draft.', 'info')
                    return redirect(url_for('admin.edit_plan', id=plan.id))
                flash(f'House plan "{plan.title}" has been updated successfully!', 'success')
                return redirect(url_for('admin.plans'))

        return render_template('admin/edit_plan.html', form=form, plan=plan)

    except Exception:
        db.session.rollback()
        print(traceback.format_exc())
        current_app.logger.error('Fatal error in edit_plan route for id=%s', id, exc_info=True)
        flash('An unexpected error occurred while loading the edit page. Please try again or contact support.', 'danger')
        return redirect(url_for('admin.plans'))


@admin_bp.route('/plans/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_plan(id):
    """Delete house plan"""

    if current_user.role != 'superadmin':
        flash('Only the Owner can delete plans.', 'warning')
        return redirect(request.referrer or url_for('admin.plans'))

    plan = db.session.get(HousePlan, id)
    if not plan:
        flash('Plan not found.', 'warning')
        return redirect(request.referrer or url_for('admin.plans'))

    plan_title = getattr(plan, 'title', '')

    try:
        # Protect data integrity: if a plan has completed purchases, do not delete it.
        # Orders.plan_id is NOT nullable and has no ondelete cascade.
        order_count = Order.query.filter_by(plan_id=id).count()
        if order_count:
            flash(
                f'Cannot delete "{plan_title}" because it has {order_count} order(s). Unpublish it instead.',
                'warning',
            )
            return redirect(request.referrer or url_for('admin.plans'))

        # Remove many-to-many category links first.
        db.session.execute(
            house_plan_categories.delete().where(house_plan_categories.c.plan_id == id)
        )

        db.session.delete(plan)
        db.session.commit()
        flash(f'Plan "{plan_title}" deleted.', 'success')
    except Exception as exc:
        db.session.rollback()
        print(traceback.format_exc())
        current_app.logger.error('Failed to delete plan %s: %s', id, exc)
        flash('Unable to delete the plan. Please try again.', 'danger')

    return redirect(request.referrer or url_for('admin.plans'))


@admin_bp.route('/plans/<int:id>/toggle-publish', methods=['POST'])
@login_required
@admin_required
def toggle_plan_publish(id):
    """Publish/unpublish a plan (public catalog only shows published plans)."""

    if current_user.role != 'superadmin':
        flash('Only the Owner can publish plans.', 'warning')
        return redirect(request.referrer or url_for('admin.plans'))

    plan = db.session.get(HousePlan, id)
    if not plan:
        flash('Plan not found.', 'warning')
        return redirect(request.referrer or url_for('admin.plans'))

    try:
        plan.is_published = not bool(plan.is_published)
        db.session.commit()
        if plan.is_published:
            flash(f'Plan "{plan.title}" is now published.', 'success')
        else:
            flash(f'Plan "{plan.title}" has been unpublished (draft).', 'info')
    except Exception as exc:
        db.session.rollback()
        print(traceback.format_exc())
        current_app.logger.error('Failed to toggle publish for plan %s: %s', id, exc)
        flash('Unable to update publish status. Please try again.', 'danger')

    return redirect(request.referrer or url_for('admin.plans'))


@admin_bp.route('/categories')
@login_required
@admin_required
def categories():
    """List all categories"""

    try:
        categories = Category.query.order_by(Category.name).all()

        # Count plans per category in a single query (avoids N+1).
        counts = dict(
            db.session.query(
                Category.id,
                func.count(house_plan_categories.c.plan_id),
            )
            .outerjoin(house_plan_categories, Category.id == house_plan_categories.c.category_id)
            .group_by(Category.id)
            .all()
        )
        plan_counts = {c.id: int(counts.get(c.id, 0) or 0) for c in categories}
    except Exception as exc:
        db.session.rollback()
        print(traceback.format_exc())
        current_app.logger.error('Failed to load categories list: %s', exc, exc_info=True)
        flash('Unable to load categories right now. Please try again.', 'danger')
        categories = []
        plan_counts = {}

    return render_template('admin/categories_list.html', categories=categories, plan_counts=plan_counts)


@admin_bp.route('/categories/manage')
@login_required
@admin_required
def manage_categories():
    """Alias route for category management.

    This exists to provide a stable endpoint name for dashboard buttons.
    """

    try:
        return categories()
    except Exception as exc:
        db.session.rollback()
        print(traceback.format_exc())
        current_app.logger.error('Failed to render manage_categories: %s', exc, exc_info=True)
        flash('Unable to load categories right now. Please try again.', 'danger')
        return redirect(url_for('admin.dashboard'))


@admin_bp.route('/categories/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_category():
    """Add new category"""
    
    form = CategoryForm()
    
    if form.validate_on_submit():
        name = (form.name.data or '').strip()
        if not name:
            flash('Name is required.', 'danger')
            return redirect(url_for('admin.add_category'))

        try:
            existing = (
                Category.query
                .filter(func.lower(Category.name) == func.lower(name))
                .first()
            )
        except Exception as exc:
            db.session.rollback()
            print(traceback.format_exc())
            current_app.logger.error('Failed to validate category uniqueness for %s: %s', name, exc, exc_info=True)
            flash('Unable to verify category uniqueness. Please try again.', 'danger')
            # PRG: do not return 200 on failed POST
            return redirect(url_for('admin.add_category'))

        if existing:
            flash('A category with that name already exists.', 'warning')
            # PRG: do not return 200 on failed POST
            return redirect(url_for('admin.add_category'))

        try:
            category = Category(name=name, description=form.description.data)
            category.slug = _generate_unique_category_slug(name)
            db.session.add(category)
            db.session.commit()
        except IntegrityError as exc:
            # Handles race conditions / double submits cleanly.
            db.session.rollback()
            print(traceback.format_exc())
            current_app.logger.warning('Duplicate category insert blocked for name=%s: %s', name, exc)
            flash('This category already exists (duplicate prevented).', 'warning')
            return redirect(url_for('admin.add_category'))
        except Exception as exc:
            db.session.rollback()
            print(traceback.format_exc())
            current_app.logger.error('Failed to add category %s: %s', name, exc, exc_info=True)
            flash('Unable to save the category. No changes were applied.', 'danger')
            return redirect(url_for('admin.add_category'))

        flash(f'Category "{category.name}" has been added successfully!', 'success')
        return redirect(url_for('admin.categories'))
    
    return render_template('admin/add_category.html', form=form)


@admin_bp.route('/categories/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_category(id):
    """Edit an existing category"""

    try:
        category = db.session.get(Category, id)
    except Exception as exc:
        db.session.rollback()
        print(traceback.format_exc())
        current_app.logger.error('Failed to load category id=%s for edit: %s', id, exc, exc_info=True)
        flash('Unable to load this category right now. Please try again.', 'danger')
        return redirect(url_for('admin.categories'))

    if category is None:
        abort(404)

    form = CategoryForm(obj=category, category_id=category.id)

    if form.validate_on_submit():
        try:
            name = (form.name.data or '').strip()
            category.name = name
            category.description = form.description.data
            category.slug = slugify(name)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            print(traceback.format_exc())
            current_app.logger.error('Failed to update category %s: %s', getattr(category, 'id', None), exc, exc_info=True)
            flash('Unable to update the category. Changes were rolled back.', 'danger')
        else:
            flash(f'Category "{category.name}" has been updated successfully!', 'success')
            return redirect(url_for('admin.categories'))

    return render_template('admin/edit_category.html', form=form, category=category)


@admin_bp.route('/categories/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_category(id):
    """Delete a category (and detach it from plans)"""

    try:
        category = db.session.get(Category, id)
        if category is None:
            abort(404)
        name = category.name

        # Safe delete: remove association rows first so plans remain intact.
        # (This avoids loading every related plan into memory.)
        db.session.execute(
            house_plan_categories.delete().where(house_plan_categories.c.category_id == id)
        )

        db.session.delete(category)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        print(traceback.format_exc())
        current_app.logger.error('Failed to delete category %s: %s', id, exc, exc_info=True)
        flash('Unable to delete the category. No changes were made.', 'danger')
    else:
        flash(f'Category "{name}" has been deleted.', 'success')
    return redirect(url_for('admin.categories'))


# Backward-compat route (old URL)
@admin_bp.route('/category/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_category_legacy():
    return redirect(url_for('admin.add_category'))


@admin_bp.route('/orders')
@login_required
@admin_required
def orders():
    """List all orders"""
    
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('ORDERS_PER_PAGE', 20)
    
    orders = Order.query.order_by(Order.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('admin/orders_list.html', orders=orders)
