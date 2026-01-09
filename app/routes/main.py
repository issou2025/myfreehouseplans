"""
Main Blueprint - Public Routes

This blueprint handles all public-facing routes including:
- Homepage
- House plans listing and detail pages
- About, Contact, Privacy, Terms pages
- Sitemap
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, Response
from flask import send_file, abort
from datetime import datetime
from app.models import HousePlan, Category, Order, ContactMessage
from app.forms import ContactForm, SearchForm
from app.extensions import db, mail
from app.seo import generate_meta_tags, generate_product_schema, generate_breadcrumb_schema, generate_sitemap
from flask_mail import Message as MailMessage
from sqlalchemy import or_
import os
import mimetypes
from urllib.parse import urlparse
from app.utils.uploads import save_uploaded_file

# Create Blueprint
main_bp = Blueprint('main', __name__)


def _protected_filepath(relative_path):
    """Return absolute path to a file stored in the protected uploads folder."""
    if not relative_path:
        return None
    base = current_app.config.get('PROTECTED_UPLOAD_FOLDER')
    return os.path.join(base, relative_path)


@main_bp.route('/download/free/<int:plan_id>')
def download_free(plan_id):
    """Serve free PDF for a plan without login, but from protected storage."""
    plan = HousePlan.query.get_or_404(plan_id)
    if not plan.free_pdf_file:
        abort(404)
    path = _protected_filepath(plan.free_pdf_file)
    if not path or not os.path.exists(path):
        abort(404)
    mimetype, _ = mimetypes.guess_type(path)
    return send_file(path, as_attachment=True, download_name=os.path.basename(path), mimetype=mimetype or 'application/octet-stream')


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
    
    # Get featured plans
    featured_plans = HousePlan.query.filter_by(
        is_published=True,
        is_featured=True
    ).limit(6).all()
    
    # Get recent plans
    recent_plans = HousePlan.query.filter_by(
        is_published=True
    ).order_by(HousePlan.created_at.desc()).limit(8).all()
    
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
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = current_app.config.get('PLANS_PER_PAGE', 12)
    
    # Build query
    query = HousePlan.query.filter_by(is_published=True)
    
    # Filter by search term
    search = request.args.get('q', '').strip()
    if search:
        query = query.filter(
            or_(
                HousePlan.title.ilike(f'%{search}%'),
                HousePlan.description.ilike(f'%{search}%')
            )
        )
    
    # Filter by category
    category_slug = request.args.get('category', type=str)
    if category_slug:
        category = Category.query.filter_by(slug=category_slug).first_or_404()
        query = query.join(HousePlan.categories).filter(Category.id == category.id)
    
    # Filter by bedrooms
    min_bedrooms = request.args.get('bedrooms', type=int)
    if min_bedrooms:
        query = query.filter(HousePlan.bedrooms >= min_bedrooms)
    
    # Filter by bathrooms
    min_bathrooms = request.args.get('bathrooms', type=int)
    if min_bathrooms:
        query = query.filter(HousePlan.bathrooms >= min_bathrooms)
    
    # Sorting
    sort = request.args.get('sort', 'newest')
    if sort == 'price_low':
        query = query.order_by(HousePlan.price.asc())
    elif sort == 'price_high':
        query = query.order_by(HousePlan.price.desc())
    elif sort == 'popular':
        query = query.order_by(HousePlan.views_count.desc())
    else:  # newest
        query = query.order_by(HousePlan.created_at.desc())
    
    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    plans = pagination.items
    
    # Get all categories for filter
    categories = Category.query.all()
    
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
                         meta=meta)


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

    return render_template(
        'plans_by_category.html',
        category=category,
        categories=categories,
        plans=plans,
        meta=meta,
    )


@main_bp.route('/plan/<slug>')
def pack_detail(slug):
    """House plan detail page"""
    
    # Get plan by slug or 404
    plan = HousePlan.query.filter_by(slug=slug, is_published=True).first_or_404()
    
    # Increment view count
    plan.increment_views()
    
    # Get related plans (same category)
    category_ids = [c.id for c in getattr(plan, 'categories', [])]
    if category_ids:
        related_plans = (
            HousePlan.query
            .filter_by(is_published=True)
            .join(HousePlan.categories)
            .filter(Category.id.in_(category_ids))
            .filter(HousePlan.id != plan.id)
            .distinct()
            .limit(4)
            .all()
        )
    else:
        related_plans = (
            HousePlan.query
            .filter_by(is_published=True)
            .filter(HousePlan.id != plan.id)
            .order_by(HousePlan.id.desc())
            .limit(4)
            .all()
        )
    
    # SEO meta tags
    meta = generate_meta_tags(
        title=plan.meta_title or plan.title,
        description=plan.meta_description or plan.short_description,
        keywords=plan.meta_keywords,
        url=url_for('main.pack_detail', slug=plan.slug, _external=True),
        type='product'
    )
    
    # Structured data for product
    product_schema = generate_product_schema(plan)
    
    # Breadcrumb schema
    breadcrumbs = [
        ('Home', url_for('main.index')),
        ('Plans', url_for('main.packs')),
        (plan.title, url_for('main.pack_detail', slug=plan.slug))
    ]
    breadcrumb_schema = generate_breadcrumb_schema(breadcrumbs)
    
    return render_template('pack_detail.html',
                         plan=plan,
                         related_plans=related_plans,
                         meta=meta,
                         product_schema=product_schema,
                         breadcrumb_schema=breadcrumb_schema)


@main_bp.route('/about')
def about():
    """About page"""
    
    meta = generate_meta_tags(
        title='About',
        description='Learn how MyFreeHousePlans works, what’s included in each pack, and how we support your build.',
        url=url_for('main.about', _external=True)
    )
    
    return render_template('about.html', meta=meta)


@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    """Contact page with form"""
    
    form = ContactForm()
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
                protected_base = current_app.config.get('PROTECTED_UPLOAD_FOLDER')
                attachment_absolute = os.path.join(protected_base, saved_attachment)
                attachment_mime, _ = mimetypes.guess_type(attachment_absolute)
            except ValueError as upload_err:
                flash(str(upload_err), 'danger')
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
            flash('We could not save your message. Please email entreprise2rc@gmail.com directly.', 'danger')
            return render_template('contact.html', form=form, meta=meta, plan_options=plan_options)

        admin_email_sent = False
        email_error_text = None
        try:
            msg = MailMessage(
                subject=f"Contact Form: {form.subject.data}",
                recipients=[current_app.config['ADMIN_EMAIL']],
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
            if attachment_absolute and os.path.exists(attachment_absolute):
                with open(attachment_absolute, 'rb') as handle:
                    msg.attach(
                        os.path.basename(attachment_absolute),
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

        if admin_email_sent:
            flash('Thanks! We logged your message and notified the studio. Expect a reply within two business days.', 'success')
        else:
            flash('We saved your message but could not reach the studio mailbox automatically. Our team will review it shortly.', 'warning')
        return redirect(url_for('main.contact'))
    
    return render_template('contact.html', form=form, meta=meta, plan_options=plan_options)


@main_bp.route('/privacy')
def privacy():
    """Privacy policy page"""
    
    meta = generate_meta_tags(
        title='Privacy Policy',
        description='How MyFreeHousePlans collects and uses information, and how to contact us with privacy questions.',
        url=url_for('main.privacy', _external=True)
    )
    
    return render_template('privacy.html', meta=meta)


@main_bp.route('/terms')
def terms():
    """Terms and conditions page"""
    
    meta = generate_meta_tags(
        title='Terms & Conditions',
        description='Terms for using MyFreeHousePlans and purchasing digital plan packs through Gumroad.',
        url=url_for('main.terms', _external=True)
    )
    
    return render_template('terms.html', meta=meta)


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
