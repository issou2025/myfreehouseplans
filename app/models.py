"""
Database Models for MyFreeHousePlans Application

This module defines all database models using SQLAlchemy ORM.
Models include User, HousePlan, Category, and Order.
"""

from app.extensions import db, login_manager
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
from flask_login import UserMixin
from datetime import datetime
from slugify import slugify
from sqlalchemy.orm import synonym


house_plan_categories = db.Table(
    'house_plan_categories',
    db.Column('plan_id', db.Integer, db.ForeignKey('house_plans.id', ondelete='CASCADE'), primary_key=True),
    db.Column('category_id', db.Integer, db.ForeignKey('categories.id', ondelete='CASCADE'), primary_key=True),
    db.Index('ix_house_plan_categories_plan_id', 'plan_id'),
    db.Index('ix_house_plan_categories_category_id', 'category_id'),
)


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    try:
        if user_id is None:
            return None
        return User.query.get(int(user_id))
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return None


class User(UserMixin, db.Model):
    """User model for authentication and customer management"""
    
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, index=True)
    password_hash = db.Column('password_hash', db.String(255), nullable=False)
    password = synonym('password_hash')
    role = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    orders = db.relationship('Order', backref='customer', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set user password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password against stored hash.

        Strict verification: only accept hashed passwords and use
        :func:`werkzeug.security.check_password_hash`. Do NOT perform
        plaintext comparisons. This ensures consistent, auditable
        authentication behavior across environments.
        """
        if not self.password_hash:
            return False
        try:
            return check_password_hash(self.password_hash, password)
        except Exception:
            # Any unexpected verification error should fail safely.
            return False
    
    @property
    def is_admin(self):
        """Check if user is admin based on role"""
        return self.role == 'superadmin'
    
    def __repr__(self):
        return f'<User {self.username}>'


class Category(db.Model):
    """Category model for organizing house plans"""
    
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships (many-to-many)
    plans = db.relationship(
        'HousePlan',
        secondary=house_plan_categories,
        back_populates='categories',
        lazy='selectin',
        passive_deletes=True,
    )
    
    def __init__(self, **kwargs):
        super(Category, self).__init__(**kwargs)
        if not self.slug and self.name:
            self.slug = slugify(self.name)
    
    def __repr__(self):
        return f'<Category {self.name}>'


class HousePlan(db.Model):
    """House Plan model for architectural plan listings"""
    
    __tablename__ = 'house_plans'
    REFERENCE_PREFIX = 'MYFREEHOUSEPLANS'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(250), unique=True, nullable=False, index=True)
    reference_code = db.Column(db.String(48), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    short_description = db.Column(db.String(300))

    # Discovery / editorial depth
    plan_type = db.Column(db.String(40), index=True)
    design_philosophy = db.Column(db.Text)
    lifestyle_suitability = db.Column(db.Text)
    customization_potential = db.Column(db.Text)

    # Rich architectural characteristics (new)
    total_area_m2 = db.Column(db.Float)
    total_area_sqft = db.Column(db.Float)
    number_of_bedrooms = db.Column(db.Integer)
    number_of_bathrooms = db.Column(db.Float)
    number_of_floors = db.Column(db.Integer)
    building_width = db.Column(db.Float)
    building_length = db.Column(db.Float)
    roof_type = db.Column(db.String(100))
    structure_type = db.Column(db.String(120))
    foundation_type = db.Column(db.String(120))
    parking_spaces = db.Column(db.Integer)
    ceiling_height = db.Column(db.Float)
    construction_complexity = db.Column(db.String(30))
    estimated_construction_cost_note = db.Column(db.String(300))
    suitable_climate = db.Column(db.String(200))
    ideal_for = db.Column(db.String(200))
    main_features = db.Column(db.Text)
    room_details = db.Column(db.Text)
    construction_notes = db.Column(db.Text)
    
    # Delivery
    # Pack 1 (Free): Admin uploads a PDF. Stored server-side.
    free_pdf_file = db.Column(db.String(600))
    price_pack_1 = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    # Pack 2/3 (Paid): Admin provides Gumroad purchase links.
    gumroad_pack_2_url = db.Column(db.String(500))
    gumroad_pack_3_url = db.Column(db.String(500))

    price_pack_2 = db.Column(db.Numeric(10, 2))
    price_pack_3 = db.Column(db.Numeric(10, 2))
    zip_pack_2 = db.Column(db.String(600))
    zip_pack_3 = db.Column(db.String(600))

    # Media
    cover_image = db.Column(db.String(600))
    
    # Plan specifications
    bedrooms = db.Column(db.Integer)
    bathrooms = db.Column(db.Float)
    square_feet = db.Column(db.Integer)
    stories = db.Column(db.Integer, default=1)
    garage = db.Column(db.Integer, default=0)  # Number of car spaces
    
    # Pricing
    # Legacy / display price (keeps compatibility)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    sale_price = db.Column(db.Numeric(10, 2))  # Optional sale price
    
    # Media
    main_image = db.Column(db.String(600))
    floor_plan_image = db.Column(db.String(600))
    pdf_file = db.Column(db.String(600))  # PDF plans file
    
    # SEO and metadata
    seo_title = db.Column(db.String(200))
    seo_description = db.Column(db.String(300))
    seo_keywords = db.Column(db.String(300))
    
    # Status and visibility
    is_featured = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=True)
    views_count = db.Column(db.Integer, default=0)
    
    # Relationships
    categories = db.relationship(
        'Category',
        secondary=house_plan_categories,
        back_populates='plans',
        lazy='selectin',
    )

    @property
    def category(self):
        """Return a primary category when present.

        The data model supports many-to-many categories, but some templates and
        route logic expect a single `.category` relationship. This property
        provides a safe, backward-compatible accessor that returns the first
        category or None.
        """
        try:
            return self.categories[0] if self.categories else None
        except Exception:
            return None

    @property
    def image_url(self):
        """Backward-compatible image URL accessor.

        Some routes/templates may refer to `plan.image_url`. Prefer cover_image
        when set, otherwise fall back to main_image.
        """
        try:
            return self.cover_image or self.main_image
        except Exception:
            return None
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    orders = db.relationship('Order', backref='plan', lazy='dynamic')
    messages = db.relationship('ContactMessage', backref='plan', lazy='dynamic')
    faqs = db.relationship('PlanFAQ', backref='plan', lazy='selectin', cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(HousePlan, self).__init__(**kwargs)
        # Generate slug and ensure uniqueness
        if not self.slug and self.title:
            base = slugify(self.title)
            self.slug = self._generate_unique_slug(base)

        # Provide a short description if missing
        if not self.short_description and self.description:
            self.short_description = self.description[:297] + '...' if len(self.description) > 300 else self.description

        if not self.reference_code:
            self.ensure_reference_code()

    @staticmethod
    def _generate_unique_slug(base_slug):
        """Generate a unique slug by appending a numeric suffix if needed."""
        candidate = base_slug
        index = 1
        while HousePlan.query.filter_by(slug=candidate).first() is not None:
            candidate = f"{base_slug}-{index}"
            index += 1
        return candidate
    
    @property
    def current_price(self):
        """Return sale price if available, otherwise regular price.

        Normalizes values so templates and SEO code don't crash if legacy
        records contain NULLs or non-numeric strings.
        """
        sale = self._normalize_price(self.sale_price)
        regular = self._normalize_price(self.price)
        return sale if sale is not None else regular
    
    @property
    def is_on_sale(self):
        """Check if plan is on sale"""
        sale = self._normalize_price(self.sale_price)
        regular = self._normalize_price(self.price)
        if sale is None or regular is None:
            return False
        return sale < regular
    
    def increment_views(self):
        """Increment view counter"""
        try:
            self.views_count += 1
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            try:
                current_app.logger.exception('Failed to increment views for plan %s: %s', self.id, exc)
            except RuntimeError:
                pass

    @staticmethod
    def _parse_reference_sequence(code):
        try:
            segment = code.split('-', 1)[1]
            numeric = segment.split('/', 1)[0]
            return int(numeric)
        except (ValueError, IndexError, AttributeError):
            return 0

    @classmethod
    def generate_reference_code(cls):
        """Generate the next reference code in the MYFREEHOUSEPLANS-XXXX/YYYY format."""
        year = datetime.utcnow().year
        like_pattern = f"{cls.REFERENCE_PREFIX}-%/{year}"
        existing = (
            cls.query
            .with_entities(cls.reference_code)
            .filter(cls.reference_code.like(like_pattern))
            .all()
        )
        max_seq = 0
        for (code,) in existing:
            max_seq = max(max_seq, cls._parse_reference_sequence(code))
        next_sequence = max_seq + 1
        return f"{cls.REFERENCE_PREFIX}-{next_sequence:03d}/{year}"

    def ensure_reference_code(self):
        if not self.reference_code:
            self.reference_code = self.generate_reference_code()
        return self.reference_code

    @staticmethod
    def _normalize_price(value):
        if value in (None, ''):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @property
    def pricing_tiers(self):
        """Return a structured view of pack pricing for UI rendering."""
        free_price = self._normalize_price(self.price_pack_1) or 0
        pack_2_price = self._normalize_price(self.price_pack_2)
        pack_3_price = self._normalize_price(self.price_pack_3)
        tiers = [
            {
                'pack': 1,
                'label': 'Free Pack',
                'price': free_price,
                'is_free': free_price == 0,
                'available': bool(self.free_pdf_file),
            },
            {
                'pack': 2,
                'label': 'PDF Pro Pack',
                'price': pack_2_price,
                'is_free': False,
                'available': bool(self.gumroad_pack_2_url),
            },
            {
                'pack': 3,
                'label': 'Ultimate CAD Pack',
                'price': pack_3_price,
                'is_free': False,
                'available': bool(self.gumroad_pack_3_url),
            },
        ]
        return tiers

    @property
    def has_free_download(self):
        return bool(self.free_pdf_file)

    @property
    def starting_paid_price(self):
        """Return the lowest paid tier price for marketing cards."""
        prices = [
            self.sale_price,
            self.price_pack_2,
            self.price_pack_3,
            self.price,
        ]
        normalized = []
        for value in prices:
            price = self._normalize_price(value)
            if price is not None and price > 0:
                normalized.append(price)
        return min(normalized) if normalized else None

    def default_faqs(self):
        """Return a default set of FAQ items for this plan when none are provided.

        Each item is a dict with keys: question, answer, pack_context.
        Answers reference the plan's reference code when helpful.
        """
        ref = self.reference_code or (self.ensure_reference_code() if hasattr(self, 'ensure_reference_code') else '')
        base = [
            {
                'question': 'Can I modify this house plan?',
                'answer': f'Yes. The plan with reference {ref} can be adapted by a local architect or engineer to meet local codes and site conditions. We recommend working with a licensed professional for permit-ready changes.',
                'pack_context': ''
            },
            {
                'question': 'What files are included in each package?',
                'answer': 'Free Pack: PDF sampler. Pro Pack: full PDF set. Ultimate Pack: editable CAD/BIM files where available (DWG, IFC). See the pack comparison above for exact contents.',
                'pack_context': ''
            },
            {
                'question': 'Is this plan suitable for my country or climate?',
                'answer': 'Plans are designed with flexible details; suitability depends on local codes, climate, and site. Reference the plan code when consulting a local engineer: ' + ref,
                'pack_context': ''
            },
            {
                'question': 'Can an architect or engineer adapt this plan?',
                'answer': 'Absolutely. Provide them with the plan files (reference ' + ref + ') and they can prepare permit-ready drawings and calculations as required locally.',
                'pack_context': ''
            },
            {
                'question': 'How do I receive the files after purchase?',
                'answer': 'Files are delivered as downloads immediately after purchase and remain available in your account. We also email a download link for convenience.',
                'pack_context': ''
            },
            {
                'question': 'What is the difference between Pack Free, Pro, and Ultimate?',
                'answer': 'Free: preview PDF. Pro: complete PDF documentation. Ultimate: editable CAD/BIM datasets for contractors and consultants. Choose the pack matching your stage and local team needs.',
                'pack_context': ''
            },
            {
                'question': 'Can I use this plan for construction immediately?',
                'answer': 'The plan is a strong starting point, but you must verify local codes, obtain permits, and possibly adapt details; consult a local architect/engineer before construction.',
                'pack_context': ''
            },
            {
                'question': 'Can I request customization for this plan?',
                'answer': 'Yes — we offer customization services. Quote requests should reference ' + ref + ' so we can estimate time and cost accurately.',
                'pack_context': ''
            },
        ]
        return base

    @staticmethod
    def _sqft_from_m2(m2_value):
        try:
            return float(m2_value) * 10.7639
        except Exception:
            return None

    @staticmethod
    def _m2_from_sqft(sqft_value):
        try:
            return float(sqft_value) / 10.7639
        except Exception:
            return None

    @property
    def area_sqft(self):
        """Preferred area in square feet (new fields first, then legacy)."""
        if self.total_area_sqft:
            return self.total_area_sqft
        if self.square_feet:
            return float(self.square_feet)
        if self.total_area_m2:
            return self._sqft_from_m2(self.total_area_m2)
        return None

    @property
    def area_m2(self):
        """Preferred area in square meters (new fields first, then derived)."""
        if self.total_area_m2:
            return self.total_area_m2
        if self.total_area_sqft:
            return self._m2_from_sqft(self.total_area_sqft)
        if self.square_feet:
            return self._m2_from_sqft(self.square_feet)
        return None

    @property
    def bedrooms_count(self):
        return self.number_of_bedrooms if self.number_of_bedrooms is not None else self.bedrooms

    @property
    def bathrooms_count(self):
        return self.number_of_bathrooms if self.number_of_bathrooms is not None else self.bathrooms

    @property
    def floors_count(self):
        return self.number_of_floors if self.number_of_floors is not None else self.stories

    @property
    def parking_count(self):
        return self.parking_spaces if self.parking_spaces is not None else self.garage

    @property
    def dimensions_summary(self):
        """Return a human-friendly building footprint summary."""
        if self.building_width and self.building_length:
            return f"{self.building_width:g} m × {self.building_length:g} m"
        if self.building_width:
            return f"Width {self.building_width:g} m"
        if self.building_length:
            return f"Length {self.building_length:g} m"
        return None

    @property
    def architectural_summary(self):
        """Short, client-facing summary used in the hero section."""
        if self.short_description:
            return self.short_description

        parts = []
        if self.floors_count:
            parts.append(f"{int(self.floors_count)}-level")
        if self.bedrooms_count:
            parts.append(f"{int(self.bedrooms_count)}-bed")
        if self.bathrooms_count:
            try:
                b = float(self.bathrooms_count)
                parts.append(f"{b:g}-bath")
            except (ValueError, TypeError) as exc:
                try:
                    current_app.logger.warning(
                        'Invalid bathrooms_count for plan %s: %s (value: %r)',
                        self.id, exc, self.bathrooms_count
                    )
                except (RuntimeError, Exception):
                    pass
        if self.roof_type:
            parts.append(f"{self.roof_type.strip().lower()} roof")
        if parts:
            return "A practical " + ", ".join(parts) + " layout designed for straightforward construction and comfortable day-to-day living."

        return "A well-balanced house plan designed for comfortable living and clear, buildable documentation."

    # SEO helper properties
    @property
    def meta_title(self):
        """Return SEO title for templates"""
        return self.seo_title or self.title

    @property
    def meta_description(self):
        """Return SEO description for templates"""
        return self.seo_description or self.short_description or ''

    @property
    def meta_keywords(self):
        """Return SEO keywords for templates"""
        return self.seo_keywords or ''

    def __repr__(self):
        return f'<HousePlan {self.title}>'


class PlanFAQ(db.Model):
    """FAQ entries associated with a specific HousePlan."""

    __tablename__ = 'plan_faqs'

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('house_plans.id', ondelete='CASCADE'), nullable=True, index=True)
    reference_code = db.Column(db.String(80), nullable=True, index=True)
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    pack_context = db.Column(db.String(20), nullable=True)  # 'free', 'pro', 'ultimate' or empty
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def as_structured(self):
        return {
            '@type': 'Question',
            'name': self.question,
            'acceptedAnswer': {
                '@type': 'Answer',
                'text': self.answer
            }
        }

    def __repr__(self):
        return f'<PlanFAQ {self.id} for plan={self.plan_id or self.reference_code}>'


class Order(db.Model):
    """Order model for tracking purchases"""
    
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    
    # Foreign keys
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('house_plans.id'), nullable=False)
    
    # Order details
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    status = db.Column(db.String(50), default='pending')  # pending, completed, failed, refunded
    
    # Payment information
    payment_method = db.Column(db.String(50))
    payment_status = db.Column(db.String(50), default='pending')
    transaction_id = db.Column(db.String(200))
    
    # Customer information
    billing_email = db.Column(db.String(120), nullable=False)
    billing_name = db.Column(db.String(200))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    
    def __init__(self, **kwargs):
        super(Order, self).__init__(**kwargs)
        if not self.order_number:
            # Generate unique order number
            self.order_number = f"ORD-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    
    @property
    def is_completed(self):
        """Check if order is completed"""
        return self.status == 'completed'
    
    def __repr__(self):
        return f'<Order {self.order_number}>'


class ContactMessage(db.Model):
    """Store inbound contact form submissions for admin follow-up."""

    __tablename__ = 'messages'

    STATUS_NEW = 'new'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_RESPONDED = 'responded'
    STATUS_ARCHIVED = 'archived'
    STATUS_CHOICES = (
        (STATUS_NEW, 'New'),
        (STATUS_IN_PROGRESS, 'In progress'),
        (STATUS_RESPONDED, 'Responded'),
        (STATUS_ARCHIVED, 'Archived'),
    )

    EMAIL_PENDING = 'pending'
    EMAIL_SENT = 'sent'
    EMAIL_FAILED = 'failed'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), nullable=False, index=True)
    phone = db.Column(db.String(40))
    subject = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    inquiry_type = db.Column(db.String(40), nullable=False)
    reference_code = db.Column(db.String(60))
    subscribe = db.Column(db.Boolean, default=False)

    plan_id = db.Column(db.Integer, db.ForeignKey('house_plans.id', ondelete='SET NULL'))
    plan_snapshot = db.Column(db.String(255))

    attachment_path = db.Column(db.String(300))
    attachment_name = db.Column(db.String(255))
    attachment_mime = db.Column(db.String(120))

    status = db.Column(db.String(20), nullable=False, default=STATUS_NEW, index=True)
    status_updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    responded_at = db.Column(db.DateTime)

    email_status = db.Column(db.String(20), nullable=False, default=EMAIL_PENDING)
    email_error = db.Column(db.Text)

    admin_notes = db.Column(db.Text)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, server_default=db.func.now(), index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_messages_status_created', 'status', 'created_at'),
    )

    def mark_status(self, new_status):
        """Update status while keeping timestamps consistent."""
        if new_status not in {choice for choice, _ in self.STATUS_CHOICES}:
            return
        if self.status != new_status:
            self.status = new_status
            self.status_updated_at = datetime.utcnow()
            if new_status == self.STATUS_RESPONDED and not self.responded_at:
                self.responded_at = datetime.utcnow()

    @property
    def has_attachment(self):
        return bool(self.attachment_path)

    @property
    def is_open(self):
        return self.status in {self.STATUS_NEW, self.STATUS_IN_PROGRESS}

    def __repr__(self):
        return f'<ContactMessage {self.id} {self.subject!r}>'


class Visitor(db.Model):
    """Lightweight visitor analytics record for admin dashboard."""

    __tablename__ = 'visitors'

    id = db.Column(db.Integer, primary_key=True)
    visit_date = db.Column(db.Date, nullable=False, index=True)
    visitor_name = db.Column(db.String(120))
    email = db.Column(db.String(200))
    ip_address = db.Column(db.String(64), nullable=False)
    user_agent = db.Column(db.String(500))
    page_visited = db.Column(db.String(255), nullable=False, index=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=db.func.now(),
        index=True,
    )

    def __repr__(self):
        return f"<Visitor {self.visit_date} {self.page_visited}>"
