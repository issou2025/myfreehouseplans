"""
Blog Blueprint - Public and Admin Routes
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError
from slugify import slugify

from app.extensions import db
from app.forms import PowerfulPostForm
from app.models import BlogPost, HousePlan, Category
from app.seo import generate_meta_tags
from app.utils.uploads import save_uploaded_file

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

    meta = generate_meta_tags(
        title=post.meta_title or post.title,
        description=post.meta_description or '',
        url=url_for('blog.detail', slug=post.slug, _external=True),
        type='article',
    )

    popular_plans = HousePlan.query.filter_by(is_published=True).order_by(HousePlan.views_count.desc()).limit(4).all()

    return render_template(
        'blog/detail.html',
        post=post,
        popular_plans=popular_plans,
        meta=meta,
    )


@blog_bp.route('/admin/blog/new', methods=['GET', 'POST'])
@login_required
@admin_required
def create():
    form = PowerfulPostForm()

    if form.validate_on_submit():
        slug_source = (form.slug.data or '').strip() or form.title.data
        slug_value = _generate_unique_slug(slug_source)

        cover_path = None
        if form.cover_image.data:
            cover_path = save_uploaded_file(form.cover_image.data, folder='blog')

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
            flash('Blog post created successfully.', 'success')
            return redirect(url_for('blog.edit', post_id=post.id))
        except IntegrityError:
            db.session.rollback()
            flash('A post with this slug already exists. Please choose another.', 'danger')

    return render_template('admin/create_post.html', form=form)


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

    if form.validate_on_submit():
        slug_source = (form.slug.data or '').strip() or post.slug
        slug_value = _generate_unique_slug(slug_source, exclude_id=post.id)
        cover_path = post.cover_image
        if form.cover_image.data:
            cover_path = save_uploaded_file(form.cover_image.data, folder='blog')

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
            flash('Blog post updated successfully.', 'success')
            return redirect(url_for('blog.edit', post_id=post.id))
        except IntegrityError:
            db.session.rollback()
            flash('A post with this slug already exists. Please choose another.', 'danger')

    return render_template('admin/create_post.html', form=form, post=post)
