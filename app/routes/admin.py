"""
Admin Blueprint - Administrative Routes

This blueprint handles administrative functionality including:
- Admin dashboard
- House plan management (CRUD)
- Category management
- Order management
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, send_file, abort, session
from flask_login import login_required, current_user, login_user, logout_user
from functools import wraps
import os
from app.models import HousePlan, Category, Order, User, ContactMessage, Visitor
from app.forms import HousePlanForm, CategoryForm, LoginForm, MessageStatusForm
from app.forms import PlanFAQForm
from app.extensions import db
from datetime import datetime, date, timedelta
from sqlalchemy import or_, func
from slugify import slugify
from urllib.parse import urlparse
from app.utils.uploads import save_uploaded_file, resolve_protected_upload
from app.domain.plan_policy import diagnose_plan, diagnostics_to_flash_messages
from sqlalchemy.exc import OperationalError, IntegrityError
from app.utils.media import is_absolute_url
from app.models import PlanFAQ
from werkzeug.security import generate_password_hash
from app.utils.db_resilience import with_db_resilience, safe_db_query

# Create Blueprint
admin_bp = Blueprint('admin', __name__)


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

    # If a logged-in user is not admin, force logout to enforce policy.
    if current_user.is_authenticated and current_user.role != 'superadmin':
        logout_user()
        flash('Admin access only. Please contact support if you need credentials.', 'warning')

    if current_user.is_authenticated and current_user.role == 'superadmin':
        return redirect(url_for('admin.dashboard'))

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

        if not user or user.role != 'superadmin' or not user.check_password(form.password.data):
            flash('Invalid administrator credentials.', 'danger')
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
            next_page = url_for('admin.dashboard')
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
        }
        
        status_labels = dict(ContactMessage.STATUS_CHOICES)

        return render_template('admin/dashboard.html',
                             stats=stats,
                             recent_orders=recent_orders,
                             popular_plans=popular_plans,
                             plan_table=plan_table,
                             recent_messages=recent_messages,
                             inbox_counts=inbox_counts,
                         inquiry_labels=INQUIRY_LABELS,
                         status_labels=status_labels)
    except Exception as e:
        current_app.logger.error('Admin dashboard query failed: %s', e)
        flash('Dashboard temporarily unavailable. Database may be initializing.', 'warning')
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
                             inquiry_labels=INQUIRY_LABELS,
                             status_labels={})


@admin_bp.route('/visitors')
@login_required
@admin_required
def visitors():
    """Visitor analytics dashboard."""

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    per_page = max(10, min(per_page, 100))

    pagination = (
        Visitor.query
        .order_by(Visitor.visit_date.desc(), Visitor.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    today = date.today()
    week_start = today - timedelta(days=6)

    stats = {
        'today': Visitor.query.filter(Visitor.visit_date == today).count(),
        'week': Visitor.query.filter(Visitor.visit_date >= week_start).count(),
        'total': Visitor.query.count(),
    }

    page_dates = {visit.visit_date for visit in pagination.items}
    date_counts = {}
    if page_dates:
        rows = (
            db.session.query(Visitor.visit_date, func.count(Visitor.id))
            .filter(Visitor.visit_date.in_(page_dates))
            .group_by(Visitor.visit_date)
            .all()
        )
        date_counts = {visit_date: count for visit_date, count in rows}

    query_args = request.args.to_dict(flat=True)
    query_args.pop('page', None)

    return render_template(
        'admin/visitors.html',
        visitors=pagination.items,
        pagination=pagination,
        stats=stats,
        date_counts=date_counts,
        query_args=query_args,
    )


@admin_bp.route('/')
@login_required
@admin_required
def admin_index():
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/plans')
@login_required
@admin_required
def plans():
    """List all house plans"""
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = max(10, min(per_page, 100))

    query = HousePlan.query

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
    stats = {
        'total': HousePlan.query.count(),
        'published': HousePlan.query.filter_by(is_published=True).count(),
        'draft': HousePlan.query.filter_by(is_published=False).count(),
        'free': HousePlan.query.filter(HousePlan.free_pdf_file.isnot(None)).count(),
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

    status_filter = request.args.get('status', 'open')
    inquiry_filter = request.args.get('type', '')
    search = request.args.get('q', '').strip()

    query = ContactMessage.query.order_by(ContactMessage.created_at.desc())

    if status_filter == 'open':
        query = query.filter(ContactMessage.status.in_(OPEN_INBOX_STATUSES))
    elif status_filter and status_filter != 'all':
        query = query.filter(ContactMessage.status == status_filter)

    if inquiry_filter:
        query = query.filter(ContactMessage.inquiry_type == inquiry_filter)

    if search:
        like_pattern = f"%{search}%"
        query = query.filter(
            or_(
                ContactMessage.subject.ilike(like_pattern),
                ContactMessage.email.ilike(like_pattern),
                ContactMessage.name.ilike(like_pattern),
                ContactMessage.reference_code.ilike(like_pattern),
            )
        )

    messages_page = query.paginate(page=page, per_page=per_page, error_out=False)

    status_counts = {
        'all': ContactMessage.query.count(),
        'open': ContactMessage.query.filter(ContactMessage.status.in_(OPEN_INBOX_STATUSES)).count(),
        ContactMessage.STATUS_NEW: ContactMessage.query.filter_by(status=ContactMessage.STATUS_NEW).count(),
        ContactMessage.STATUS_RESPONDED: ContactMessage.query.filter_by(status=ContactMessage.STATUS_RESPONDED).count(),
        ContactMessage.STATUS_ARCHIVED: ContactMessage.query.filter_by(status=ContactMessage.STATUS_ARCHIVED).count(),
    }

    status_options = [
        ('open', 'Open'),
        ('all', 'All'),
    ] + list(ContactMessage.STATUS_CHOICES)

    inquiry_options = [('', 'All topics')] + [(key, label) for key, label in INQUIRY_LABELS.items()]

    filters = {
        'status': status_filter,
        'type': inquiry_filter,
        'q': search,
        'per_page': per_page,
    }

    query_args = request.args.to_dict(flat=True)
    query_args.pop('page', None)

    status_labels = dict(ContactMessage.STATUS_CHOICES)

    return render_template(
        'admin/messages_list.html',
        messages=messages_page.items,
        pagination=messages_page,
        filters=filters,
        status_counts=status_counts,
        status_options=status_options,
        inquiry_options=inquiry_options,
        inquiry_labels=INQUIRY_LABELS,
        query_args=query_args,
        status_labels=status_labels,
    )


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
@admin_required
def add_plan():
    """Add new house plan"""
    
    form = HousePlanForm()
    
    categories = Category.query.order_by(Category.name).all()
    if not categories:
        flash('Please create at least one category first.', 'warning')
        return redirect(url_for('admin.categories'))
    form.category_ids.choices = [(c.id, c.name) for c in categories]
    
    if request.method == 'POST':
        current_app.logger.info('Session before POST: user_id=%s, username=%s, role=%s, permanent=%s', 
                               session.get('user_id'), session.get('username'), session.get('role'), session.permanent)
    
    if form.validate_on_submit():
        plan = HousePlan(
            title=form.title.data,
            description=form.description.data,
            short_description=form.short_description.data,
            plan_type=form.plan_type.data or None,
            bedrooms=form.bedrooms.data,
            bathrooms=form.bathrooms.data,
            stories=form.stories.data,
            garage=form.garage.data,
            price=form.price.data,
            sale_price=form.sale_price.data,
            price_pack_1=form.price_pack_1.data if form.price_pack_1.data is not None else 0,
            price_pack_2=form.price_pack_2.data,
            price_pack_3=form.price_pack_3.data,
            is_featured=form.is_featured.data,
            is_published=form.is_published.data
        )

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
            if getattr(form, 'save_draft', None) and form.save_draft.data:
                plan.is_published = False

            db.session.add(plan)
            db.session.commit()
        except ValueError as upload_error:
            db.session.rollback()
            flash(str(upload_error), 'danger')
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception('Failed to add plan "%s": %s', form.title.data, exc)
            flash('Unable to save the plan. No data was written.', 'danger')
        else:
            # Provide specific feedback and redirect depending on whether this
            # was an explicit "Save Draft" action or a full publish/save.
            if getattr(form, 'save_draft', None) and form.save_draft.data:
                flash(f'House plan "{plan.title}" has been saved as a draft.', 'info')
                current_app.logger.info('Session after POST (draft save): user_id=%s, username=%s, role=%s, permanent=%s',
                                        session.get('user_id'), session.get('username'), session.get('role'), session.permanent)
                return redirect(url_for('admin.edit_plan', id=plan.id))
            else:
                flash(f'House plan "{plan.title}" has been added successfully!', 'success')
                current_app.logger.info('Session after POST: user_id=%s, username=%s, role=%s, permanent=%s', 
                                       session.get('user_id'), session.get('username'), session.get('role'), session.permanent)
                return redirect(url_for('admin.plans'))
    
    return render_template('admin/add_plan.html', form=form)


@admin_bp.route('/plans/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_plan(id):
    """Edit existing house plan - fully bulletproofed"""

    try:
        # Load plan
        try:
            plan = HousePlan.query.get(id)
        except Exception:
            current_app.logger.exception('Failed to load plan id=%s for edit (DB/query error)', id)
            flash('Unable to load this plan right now (database error). Please try again.', 'danger')
            return redirect(url_for('admin.plans'))

        if plan is None:
            flash('House plan not found.', 'warning')
            return redirect(url_for('admin.plans'))

        # Initialize form
        form = HousePlanForm(obj=plan)

        # Load categories
        try:
            categories = Category.query.order_by(Category.name).all()
        except Exception:
            current_app.logger.exception('Failed to load categories while editing plan id=%s', id)
            categories = []
            flash('Categories could not be loaded (database error). You can still edit other fields.', 'warning')

        form.category_ids.choices = [(c.id, c.name) for c in categories]
        
        # Prefill categories on GET
        if request.method == 'GET':
            try:
                form.category_ids.data = [c.id for c in (plan.categories or [])]
            except Exception:
                current_app.logger.exception('Failed to prefill category_ids for plan id=%s', id)
                form.category_ids.data = []
    
        if form.validate_on_submit():
            try:
                plan.title = form.title.data
                plan.description = form.description.data
                plan.short_description = form.short_description.data
                plan.plan_type = form.plan_type.data or None
                plan.bedrooms = form.bedrooms.data
                plan.bathrooms = form.bathrooms.data
                plan.stories = form.stories.data
                plan.garage = form.garage.data
                plan.price = form.price.data
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
                category_ids = form.category_ids.data or []
                if category_ids:
                    try:
                        selected_categories = Category.query.filter(Category.id.in_(category_ids)).all()
                    except Exception:
                        current_app.logger.exception('Failed to load selected categories for plan id=%s; category_ids=%s', plan.id, category_ids)
                        selected_categories = []
                        flash('Selected categories could not be saved (database error).', 'warning')
                else:
                    selected_categories = []
                plan.categories = selected_categories
                plan.is_featured = form.is_featured.data
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
                
                plan.updated_at = datetime.utcnow()

                # If the admin clicked "Save Draft", ensure the plan remains unpublished
                if getattr(form, 'save_draft', None) and form.save_draft.data:
                    plan.is_published = False

                db.session.commit()
            except ValueError as upload_error:
                db.session.rollback()
                flash(str(upload_error), 'danger')
            except Exception as exc:
                db.session.rollback()
                current_app.logger.exception('Failed to update plan %s: %s', plan.id, exc)
                flash('Unable to update the plan. Your changes were not saved.', 'danger')
            else:
                if getattr(form, 'save_draft', None) and form.save_draft.data:
                    flash(f'House plan "{plan.title}" has been saved as a draft.', 'info')
                    return redirect(url_for('admin.edit_plan', id=plan.id))
                flash(f'House plan "{plan.title}" has been updated successfully!', 'success')
                return redirect(url_for('admin.plans'))
    
        return render_template('admin/edit_plan.html', form=form, plan=plan)
    
    except Exception as fatal_exc:
        # Catch-all for any unexpected errors (form init, template rendering, etc.)
        current_app.logger.exception('Fatal error in edit_plan route for id=%s', id)
        flash('An unexpected error occurred while loading the edit page. Please try again or contact support.', 'danger')
        return redirect(url_for('admin.plans'))


@admin_bp.route('/plans/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_plan(id):
    """Delete house plan"""
    flash('Deleting plans is disabled to protect live catalog data.', 'warning')
    return redirect(url_for('admin.plans'))


@admin_bp.route('/categories')
@login_required
@admin_required
def categories():
    """List all categories"""

    categories = Category.query.order_by(Category.name).all()
    # Count plans per category (fast, single query)
    plan_counts = {
        c.id: HousePlan.query.filter(HousePlan.categories.any(Category.id == c.id)).count()
        for c in categories
    }
    return render_template('admin/categories_list.html', categories=categories, plan_counts=plan_counts)


@admin_bp.route('/categories/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add_category():
    """Add new category"""
    
    form = CategoryForm()
    
    if form.validate_on_submit():
        name = (form.name.data or '').strip()
        category = Category(name=name, description=form.description.data)
        category.slug = slugify(name)
        try:
            db.session.add(category)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception('Failed to add category %s: %s', name, exc)
            flash('Unable to save the category. No changes were applied.', 'danger')
        else:
            flash(f'Category "{category.name}" has been added successfully!', 'success')
            return redirect(url_for('admin.categories'))
    
    return render_template('admin/add_category.html', form=form)


@admin_bp.route('/categories/edit/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_category(id):
    """Edit an existing category"""

    category = Category.query.get_or_404(id)
    form = CategoryForm(obj=category, category_id=category.id)

    if form.validate_on_submit():
        name = (form.name.data or '').strip()
        category.name = name
        category.description = form.description.data
        category.slug = slugify(name)
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            current_app.logger.exception('Failed to update category %s: %s', category.id, exc)
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

    category = Category.query.get_or_404(id)
    name = category.name
    # Detach from plans to avoid orphan association issues
    try:
        category.plans = []
        db.session.delete(category)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Failed to delete category %s: %s', id, exc)
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
