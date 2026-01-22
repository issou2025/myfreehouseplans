"""Blog Blueprint - Public and Admin Routes."""

from io import BytesIO

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort, send_file
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError
from slugify import slugify

from app.extensions import db
from app.forms import PowerfulPostForm
from app.models import BlogPost, HousePlan, Category
from app.seo import generate_meta_tags
from app.utils.uploads import save_uploaded_file
from app.utils.experience_links import experience_for_article, get_experience_options
from app.utils.article_extras import (
    extract_article_extras_from_form,
    load_article_extras,
    normalize_article_extras,
    save_article_extras,
)
from app.services.blog.article_pdf import ArticlePdfInput, build_article_pdf

blog_bp = Blueprint('blog', __name__)


def admin_required(f):
    """Decorator to require admin privileges."""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'superadmin':
            flash('Administrator login required.', 'warning')
            return redirect(url_for('admin.admin_login', next=request.url))
        return f(*args, **kwargs)

    return decorated_function


def _generate_unique_slug(title, *, exclude_id=None):
    base = slugify(title) or 'post'
    candidate = base
    suffix = 2
    while True:
        query = BlogPost.query.filter_by(slug=candidate)
        if exclude_id is not None:
            query = query.filter(BlogPost.id != exclude_id)
        if query.first() is None:
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


@blog_bp.route('/blog')
def index():
    page = request.args.get('page', 1, type=int)
    query = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()

    posts_query = BlogPost.query.filter_by(status=BlogPost.STATUS_PUBLISHED)

    if query:
        like = f"%{query}%"
        posts_query = posts_query.filter(
            or_(BlogPost.title.ilike(like), BlogPost.content.ilike(like))
        )

    if category:
        posts_query = (
            posts_query
            .join(BlogPost.linked_plan)
            .join(HousePlan.categories)
            .filter(Category.slug == category)
        )

    # Random display for a fresher editorial experience.
    # NOTE: keep deterministic ordering when filtering/searching to avoid
    # confusing pagination results.
    if not query and not category:
        posts_query = posts_query.order_by(func.random())
    else:
        posts_query = posts_query.order_by(BlogPost.created_at.desc())
    pagination = posts_query.paginate(page=page, per_page=9, error_out=False)

    meta = generate_meta_tags(
        title='Blog',
        description='Architecture insights and curated plan guides.',
        url=url_for('blog.index', _external=True),
        type='article',
    )

    try:
        categories = Category.query.order_by(Category.name.asc()).all()
    except Exception:
        categories = []

    popular_plans = HousePlan.query.filter_by(is_published=True).order_by(HousePlan.views_count.desc()).limit(4).all()

    return render_template(
        'blog/index.html',
        posts=pagination.items,
        pagination=pagination,
        query=query,
        category=category,
        categories=categories,
        popular_plans=popular_plans,
        meta=meta,
    )


@blog_bp.route('/blog/<slug>')
def detail(slug):
    post = BlogPost.query.filter_by(slug=slug, status=BlogPost.STATUS_PUBLISHED).first_or_404()

    extras = {}
    try:
        extras = normalize_article_extras(load_article_extras(slug=post.slug, post_id=post.id))
    except Exception:
        extras = {}

    seo_overrides = {}
    try:
        seo_overrides = (extras or {}).get('seo') or {}
    except Exception:
        seo_overrides = {}

    meta_title = seo_overrides.get('meta_title') or post.meta_title or post.title
    meta_description = seo_overrides.get('meta_description') or post.meta_description or ''
    canonical_url = seo_overrides.get('canonical_url') or url_for('blog.detail', slug=post.slug, _external=True)

    og_image = seo_overrides.get('og_image')
    if not og_image:
        try:
            featured = (extras or {}).get('media', {}).get('featured', {}).get('url')
            if not featured:
                featured = (extras or {}).get('images', {}).get('featured')
        except Exception:
            featured = None
        og_image = featured or post.cover_image

    meta = generate_meta_tags(
        title=meta_title,
        description=meta_description,
        image=og_image,
        url=canonical_url,
        type='article',
    )

    related_experience = None
    try:
        related_experience = experience_for_article(slug=post.slug, extras=extras)
    except Exception:
        related_experience = None

    popular_plans = HousePlan.query.filter_by(is_published=True).order_by(HousePlan.views_count.desc()).limit(4).all()

    return render_template(
        'blog/detail.html',
        post=post,
        popular_plans=popular_plans,
        meta=meta,
        extras=extras,
        related_experience=related_experience,
    )


@blog_bp.route('/blog/<slug>/pdf')
def download_pdf(slug):
    post = BlogPost.query.filter_by(slug=slug, status=BlogPost.STATUS_PUBLISHED).first_or_404()

    extras = {}
    try:
        extras = normalize_article_extras(load_article_extras(slug=post.slug, post_id=post.id))
    except Exception:
        extras = {}

    canonical_url = url_for('blog.detail', slug=post.slug, _external=True)
    pdf_bytes = build_article_pdf(
        ArticlePdfInput(
            title=post.title,
            slug=post.slug,
            created_at=post.created_at,
            canonical_url=canonical_url,
            content_html=post.content or '',
            cover_image=post.cover_image,
            extras=extras or {},
        )
    )

    safe_name = f"{post.slug}.pdf"
    return send_file(
        BytesIO(pdf_bytes),
        mimetype='application/pdf',
        as_attachment=True,
        download_name=safe_name,
        max_age=60,
    )


@blog_bp.route('/admin/blog/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    form = PowerfulPostForm()

    extras = {}
    try:
        # New article: extras not persisted until after first save.
        extras = {}
    except Exception:
        extras = {}

    if form.validate_on_submit():
        slug_source = (form.slug.data or '').strip() or form.title.data
        slug_value = _generate_unique_slug(slug_source)

        cover_path = None
        cover_upload = form.cover_image.data
        if cover_upload and getattr(cover_upload, 'filename', ''):
            try:
                cover_path = save_uploaded_file(cover_upload, folder='blog')
            except ValueError as upload_err:
                flash(str(upload_err), 'danger')
                return render_template(
                    'admin/create_post.html',
                    form=form,
                    extras=extras,
                    experience_options=get_experience_options(),
                )
            except Exception as exc:
                current_app.logger.exception('Failed to upload blog cover image (create): %s', exc)
                flash('We could not upload that image. Please try a different file.', 'danger')
                return render_template(
                    'admin/create_post.html',
                    form=form,
                    extras=extras,
                    experience_options=get_experience_options(),
                )

        post = BlogPost(
            title=form.title.data.strip(),
            slug=slug_value,
            meta_title=form.meta_title.data.strip() if form.meta_title.data else None,
            meta_description=form.meta_description.data.strip() if form.meta_description.data else None,
            content=form.content.data,
            cover_image=cover_path,
            plan_id=form.plan_id.data or None,
            status=form.status.data,
        )

        try:
            db.session.add(post)
            db.session.commit()

            # Save optional extras (filesystem only). Never blocks DB success.
            try:
                extras_payload = extract_article_extras_from_form(request.form)
                full_mode = (request.form.get('extras__present') or '').strip() == '1'
                if full_mode or extras_payload:
                    save_article_extras(extras_payload, slug=post.slug, post_id=post.id)
            except Exception:
                current_app.logger.exception('Failed to save article extras (create)')

            flash('Blog post created successfully.', 'success')
            return redirect(url_for('blog.edit', post_id=post.id))
        except IntegrityError:
            db.session.rollback()
            flash('A post with this slug already exists. Please choose another.', 'danger')

    return render_template(
        'admin/create_post.html',
        form=form,
        extras=extras,
        experience_options=get_experience_options(),
    )


@blog_bp.route('/admin/blog')
@login_required
@admin_required
def admin_list():
    page = request.args.get('page', 1, type=int)
    query = (request.args.get('q') or '').strip()
    status = (request.args.get('status') or '').strip()

    posts_query = BlogPost.query
    if query:
        like = f"%{query}%"
        posts_query = posts_query.filter(
            or_(BlogPost.title.ilike(like), BlogPost.content.ilike(like))
        )
    if status:
        posts_query = posts_query.filter(BlogPost.status == status)

    posts_query = posts_query.order_by(BlogPost.created_at.desc())
    pagination = posts_query.paginate(page=page, per_page=12, error_out=False)

    return render_template(
        'admin/blog_list.html',
        posts=pagination.items,
        pagination=pagination,
        query=query,
        status=status,
    )


@blog_bp.route('/admin/blog/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(post_id):
    post = BlogPost.query.get_or_404(post_id)
    form = PowerfulPostForm(obj=post)

    extras = {}
    try:
        extras = normalize_article_extras(load_article_extras(slug=post.slug, post_id=post.id))
    except Exception:
        extras = {}

    if form.validate_on_submit():
        old_slug = post.slug
        slug_source = (form.slug.data or '').strip() or post.slug
        slug_value = _generate_unique_slug(slug_source, exclude_id=post.id)
        cover_path = post.cover_image
        cover_upload = form.cover_image.data
        if cover_upload and getattr(cover_upload, 'filename', ''):
            try:
                cover_path = save_uploaded_file(cover_upload, folder='blog')
            except ValueError as upload_err:
                flash(str(upload_err), 'danger')
                return render_template(
                    'admin/create_post.html',
                    form=form,
                    post=post,
                    extras=extras,
                    experience_options=get_experience_options(),
                )
            except Exception as exc:
                current_app.logger.exception('Failed to upload blog cover image (edit): %s', exc)
                flash('We could not upload that image. Please try a different file.', 'danger')
                return render_template(
                    'admin/create_post.html',
                    form=form,
                    post=post,
                    extras=extras,
                    experience_options=get_experience_options(),
                )

        post.title = form.title.data.strip()
        post.slug = slug_value
        post.meta_title = form.meta_title.data.strip() if form.meta_title.data else None
        post.meta_description = form.meta_description.data.strip() if form.meta_description.data else None
        post.content = form.content.data
        post.cover_image = cover_path
        post.plan_id = form.plan_id.data or None
        post.status = form.status.data

        try:
            db.session.commit()

            # Save optional extras (filesystem only). Never blocks DB success.
            try:
                extras_payload = extract_article_extras_from_form(request.form)
                full_mode = (request.form.get('extras__present') or '').strip() == '1'
                if full_mode or extras_payload:
                    save_article_extras(extras_payload, slug=post.slug, post_id=post.id)
            except Exception:
                current_app.logger.exception('Failed to save article extras (edit)')

            flash('Blog post updated successfully.', 'success')
            return redirect(url_for('blog.edit', post_id=post.id))
        except IntegrityError:
            db.session.rollback()
            flash('A post with this slug already exists. Please choose another.', 'danger')

    return render_template(
        'admin/create_post.html',
        form=form,
        post=post,
        extras=extras,
        experience_options=get_experience_options(),
    )


@blog_bp.route('/admin/blog/<int:post_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(post_id):
    """Delete a blog post (admin-only)."""

    post = BlogPost.query.get_or_404(post_id)
    try:
        db.session.delete(post)
        db.session.commit()
        flash('Blog post deleted.', 'info')
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception('Failed to delete blog post %s: %s', post_id, exc)
        flash('Unable to delete this post right now. Please try again.', 'danger')

    return redirect(url_for('blog.admin_list'))
