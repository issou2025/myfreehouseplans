"""
WTForms Form Classes for MyFreeHousePlans Application

This module defines all forms used throughout the application
for user input validation and CSRF protection.
"""

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, TextAreaField, DecimalField, IntegerField, FloatField, SelectField, SelectMultipleField, BooleanField, SubmitField
from flask_ckeditor import CKEditorField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional, NumberRange, URL
from app.models import User, Category, ContactMessage, HousePlan, BlogPost
from app.models import PlanFAQ


class LoginForm(FlaskForm):
    """User login form"""
    
    username = StringField('Username or email', validators=[
        DataRequired(message='Username or email is required'),
        Length(max=255, message='Must be 255 characters or less')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required')
    ])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Log In')


class StaffCreateForm(FlaskForm):
    """Owner-only form to create staff (assistant) accounts."""

    username = StringField('Username', validators=[
        DataRequired(message='Username is required'),
        Length(min=3, max=80, message='Username must be between 3 and 80 characters'),
    ])
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address'),
        Length(max=255, message='Must be 255 characters or less'),
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=8, message='Password must be at least 8 characters'),
    ])
    submit = SubmitField('Create staff account')

    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken. Please choose a different one.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different one.')


class RegistrationForm(FlaskForm):
    """User registration form"""
    
    username = StringField('Username', validators=[
        DataRequired(message='Username is required'),
        Length(min=3, max=80, message='Username must be between 3 and 80 characters')
    ])
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address')
    ])
    first_name = StringField('First Name', validators=[
        Length(max=100, message='First name must be less than 100 characters')
    ])
    last_name = StringField('Last Name', validators=[
        Length(max=100, message='Last name must be less than 100 characters')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=8, message='Password must be at least 8 characters')
    ])
    password_confirm = PasswordField('Confirm Password', validators=[
        DataRequired(message='Please confirm your password'),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')
    
    def validate_username(self, username):
        """Check if username already exists"""
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken. Please choose a different one.')
    
    def validate_email(self, email):
        """Check if email already exists"""
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different one.')


class ContactForm(FlaskForm):
    """Contact form for customer inquiries"""
    
    name = StringField('Name', validators=[
        DataRequired(message='Name is required'),
        Length(max=100)
    ])
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address')
    ])
    phone = StringField('Phone Number', validators=[
        Length(max=20)
    ])
    subject = StringField('Subject', validators=[
        DataRequired(message='Subject is required'),
        Length(max=200)
    ])
    message = TextAreaField('Message', validators=[
        DataRequired(message='Message is required'),
        Length(min=10, max=2000, message='Message must be between 10 and 2000 characters')
    ])


class DXFTakeoffForm(FlaskForm):
    """Formulaire Admin: upload DXF + paramètres de métré.

    Conçu pour CivilQuant Pro.
    - Statut: sans persistance DB (le traitement est côté serveur et les résultats peuvent être mis en session).
    """

    dxf_file = FileField(
        'Fichier DXF (.dxf)',
        validators=[
            FileRequired(message='Veuillez sélectionner un fichier DXF.'),
            FileAllowed(['dxf'], message='Format non supporté. Seuls les fichiers .dxf sont autorisés.'),
        ],
    )

    wall_height_m = FloatField(
        'Hauteur des murs (m)',
        validators=[
            DataRequired(message='La hauteur des murs est requise.'),
            NumberRange(min=0.5, max=20.0, message='Hauteur des murs invalide.'),
        ],
        default=2.8,
    )

    scale = SelectField(
        'Échelle / unités du dessin',
        choices=[
            ('meters', 'Mètres (m)'),
            ('centimeters', 'Centimètres (cm)'),
            ('millimeters', 'Millimètres (mm)'),
        ],
        validators=[DataRequired(message='Veuillez choisir une unité de dessin.')],
        default='millimeters',
    )

    submit = SubmitField('Analyser le DXF')

    website = StringField('Website', validators=[Optional(), Length(max=120)])
    inquiry_type = SelectField(
        'Inquiry type',
        choices=[
            ('plans', 'Plan selection & availability'),
            ('orders', 'Gumroad orders & downloads'),
            ('custom', 'Custom project or collaboration'),
            ('support', 'Technical support'),
        ],
        validators=[DataRequired(message='Please choose the topic that best fits your message.')],
    )
    plan_reference = SelectField('Plan of interest', choices=[], validators=[Optional()], default='', coerce=str)
    reference_code = StringField('Reference code (optional)', validators=[Optional(), Length(max=50)])
    attachment = FileField('Attachment', validators=[
        Optional(),
        FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'gif', 'dwg', 'doc', 'docx'], 'Upload PDF, DOC/DOCX, DWG, or image files only.'),
    ])
    subscribe = BooleanField('Send me quarterly studio updates')
    submit = SubmitField('Send Message')


class MessageStatusForm(FlaskForm):
    """Admin form to update contact message status and notes."""

    status = SelectField('Status', validators=[DataRequired(message='Please choose a status')])
    admin_notes = TextAreaField('Internal notes', validators=[Optional(), Length(max=2000)])
    submit = SubmitField('Update Message')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status.choices = [(value, label) for value, label in ContactMessage.STATUS_CHOICES]


class HousePlanForm(FlaskForm):
    """Form for creating/editing house plans (Admin)"""
    
    title = StringField('Plan Title', validators=[
        DataRequired(message='Title is required'),
        Length(max=200)
    ])
    description = TextAreaField('Description', validators=[
        DataRequired(message='Description is required')
    ])
    short_description = StringField('Architectural summary (1–2 sentences)', validators=[
        Length(max=300)
    ])

    plan_type = SelectField(
        'Plan type',
        validators=[Optional()],
        choices=[
            ('', 'Select…'),
            ('family', 'Family'),
            ('rental', 'Rental / Income'),
            ('luxury', 'Luxury'),
        ],
    )

    # General overview
    total_area_m2 = FloatField('Total built area (m²)', validators=[Optional(), NumberRange(min=0)])
    total_area_sqft = FloatField('Total built area (sq ft)', validators=[Optional(), NumberRange(min=0)])
    
    # Specifications
    bedrooms = IntegerField('Bedrooms', validators=[
        Optional(),
        NumberRange(min=0, max=20, message='Bedrooms must be between 0 and 20')
    ])
    bathrooms = DecimalField('Bathrooms', validators=[
        Optional(),
        NumberRange(min=0, max=20, message='Bathrooms must be between 0 and 20')
    ])
    stories = IntegerField('Floors', validators=[
        Optional(),
        NumberRange(min=1, max=5, message='Stories must be between 1 and 5')
    ])
    garage = IntegerField('Parking spaces', validators=[
        Optional(),
        NumberRange(min=0, max=10, message='Garage spaces must be between 0 and 10')
    ])

    building_width = FloatField('Building width (m)', validators=[Optional(), NumberRange(min=0)])
    building_length = FloatField('Building length (m)', validators=[Optional(), NumberRange(min=0)])

    roof_type = StringField('Roof style', validators=[Optional(), Length(max=100)])
    structure_type = StringField('Structural system', validators=[Optional(), Length(max=120)])
    foundation_type = StringField('Foundation type', validators=[Optional(), Length(max=120)])
    ceiling_height = FloatField('Typical ceiling height (m)', validators=[Optional(), NumberRange(min=0)])

    construction_complexity = SelectField(
        'Construction complexity',
        validators=[Optional()],
        choices=[
            ('', 'Select…'),
            ('low', 'Low (simple and straightforward)'),
            ('medium', 'Medium (standard detailing)'),
            ('high', 'High (detailed / advanced)'),
        ],
    )
    estimated_construction_cost_note = StringField('Cost note (optional)', validators=[Optional(), Length(max=300)])
    suitable_climate = StringField('Suitable climate', validators=[Optional(), Length(max=200)])
    ideal_for = StringField('Ideal for', validators=[Optional(), Length(max=200)])

    main_features = TextAreaField('Main features', validators=[Optional(), Length(max=4000)])
    room_details = TextAreaField('Room-by-room description', validators=[Optional(), Length(max=6000)])
    construction_notes = TextAreaField('Construction notes', validators=[Optional(), Length(max=6000)])

    design_philosophy = TextAreaField('Design philosophy', validators=[Optional(), Length(max=6000)])
    lifestyle_suitability = TextAreaField('Lifestyle suitability', validators=[Optional(), Length(max=6000)])
    customization_potential = TextAreaField('Customization potential', validators=[Optional(), Length(max=6000)])
    
    # Professional Marketing & Positioning (Migration 0017)
    target_buyer = StringField('Target buyer persona', validators=[
        Optional(),
        Length(max=100, message='Target buyer must be 100 characters or less')
    ], description='e.g., "First-time homebuyers", "Growing families", "Retirees"')
    
    budget_category = SelectField(
        'Budget category',
        validators=[Optional()],
        choices=[
            ('', 'Select…'),
            ('Affordable', 'Affordable'),
            ('Mid-range', 'Mid-range'),
            ('Premium', 'Premium'),
            ('Luxury', 'Luxury'),
        ],
        description='Price positioning for this plan'
    )
    
    architectural_style = StringField('Architectural style', validators=[
        Optional(),
        Length(max=100, message='Style must be 100 characters or less')
    ], description='e.g., "Modern", "Traditional", "Contemporary", "Mediterranean"')
    
    key_selling_point = TextAreaField('Key selling point', validators=[
        Optional(),
        Length(max=500, message='Key selling point must be 500 characters or less')
    ], description='Main benefit or hook for marketing (1-2 sentences)')
    
    problems_this_plan_solves = TextAreaField('Problems this plan solves', validators=[
        Optional(),
        Length(max=1000, message='Must be 1000 characters or less')
    ], description='Pain points this design addresses (e.g., "Maximizes natural light in narrow lots")')
    
    # Structured Room Specifications (Migration 0017)
    living_rooms = IntegerField('Living rooms', validators=[
        Optional(),
        NumberRange(min=0, max=5, message='Living rooms must be between 0 and 5')
    ])
    
    kitchens = IntegerField('Kitchens', validators=[
        Optional(),
        NumberRange(min=0, max=3, message='Kitchens must be between 0 and 3')
    ])
    
    offices = IntegerField('Offices / Studies', validators=[
        Optional(),
        NumberRange(min=0, max=5, message='Offices must be between 0 and 5')
    ])
    
    terraces = IntegerField('Terraces / Patios', validators=[
        Optional(),
        NumberRange(min=0, max=10, message='Terraces must be between 0 and 10')
    ])
    
    storage_rooms = IntegerField('Storage rooms', validators=[
        Optional(),
        NumberRange(min=0, max=10, message='Storage rooms must be between 0 and 10')
    ])
    
    # Land Requirements (Migration 0017)
    min_plot_width = FloatField('Minimum plot width (m)', validators=[
        Optional(),
        NumberRange(min=0, message='Plot width must be positive')
    ], description='Minimum land width required for this plan')
    
    min_plot_length = FloatField('Minimum plot length (m)', validators=[
        Optional(),
        NumberRange(min=0, message='Plot length must be positive')
    ], description='Minimum land depth required for this plan')
    
    # Construction Details (Migration 0017)
    climate_compatibility = StringField('Climate compatibility', validators=[
        Optional(),
        Length(max=200, message='Climate compatibility must be 200 characters or less')
    ], description='e.g., "Tropical, Temperate", "Hot & Arid", "Cold climates"')
    
    estimated_build_time = StringField('Estimated build time', validators=[
        Optional(),
        Length(max=100, message='Build time must be 100 characters or less')
    ], description='e.g., "6-9 months", "12-18 months"')
    
    # Cost Estimation (Migration 0017)
    estimated_cost_low = DecimalField('Estimated cost (low) - USD', validators=[
        Optional(),
        NumberRange(min=0, message='Cost estimate must be positive')
    ], description='Low-end construction cost estimate')
    
    estimated_cost_high = DecimalField('Estimated cost (high) - USD', validators=[
        Optional(),
        NumberRange(min=0, message='Cost estimate must be positive')
    ], description='High-end construction cost estimate')
    
    # Pack Descriptions (Migration 0017)
    pack1_description = TextAreaField('Free Pack description', validators=[
        Optional(),
        Length(max=1000, message='Pack description must be 1000 characters or less')
    ], description='Detailed description of what\'s included in the free pack')
    
    pack2_description = TextAreaField('PDF Pro Pack description', validators=[
        Optional(),
        Length(max=1000, message='Pack description must be 1000 characters or less')
    ], description='Detailed description of what\'s included in the PDF Pro Pack')
    
    pack3_description = TextAreaField('Ultimate CAD Pack description', validators=[
        Optional(),
        Length(max=1000, message='Pack description must be 1000 characters or less')
    ], description='Detailed description of what\'s included in the Ultimate CAD Pack')
    
    # Pricing
    price_pack_1 = DecimalField('Free Pack value ($)', default=0, validators=[
        Optional(),
        NumberRange(min=0, message='Pack price cannot be negative')
    ])
    price_pack_2 = DecimalField('PDF Pro Pack price ($)', validators=[
        Optional(),
        NumberRange(min=0, message='Pack price cannot be negative')
    ])
    price_pack_3 = DecimalField('Ultimate CAD Pack price ($)', validators=[
        Optional(),
        NumberRange(min=0, message='Pack price cannot be negative')
    ])
    price = DecimalField('Display price (USD)', validators=[
        DataRequired(message='Price is required'),
        NumberRange(min=0, message='Price must be positive')
    ])
    sale_price = DecimalField('Sale Price ($)', validators=[
        Optional(),
        NumberRange(min=0, message='Sale price must be positive')
    ])

    # Gumroad purchase links (paid packs)
    gumroad_pack_2_url = StringField('Gumroad link for PDF Pro Pack', validators=[Optional(), Length(max=500), URL(message='Please enter a valid URL (including https://).')])
    gumroad_pack_3_url = StringField('Gumroad link for Ultimate CAD Pack', validators=[Optional(), Length(max=500), URL(message='Please enter a valid URL (including https://).')])
    
    # Categories (many-to-many)
    category_ids = SelectMultipleField('Categories', coerce=int)
    
    # File uploads
    cover_image = FileField('Cover Image', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'gif'], 'Images only!')
    ])
    free_pdf_file = FileField('Free PDF (metric)', validators=[
        FileAllowed(['pdf'], 'PDF files only!')
    ])
    
    # SEO
    seo_title = StringField('SEO Title', validators=[Length(max=200)])
    seo_description = TextAreaField('SEO Description', validators=[Length(max=300)])
    seo_keywords = StringField('SEO Keywords', validators=[Length(max=300)])
    
    # Status
    is_featured = BooleanField('Featured Plan')
    is_published = BooleanField('Published')

    save_draft = SubmitField('Save Draft')
    
    submit = SubmitField('Save Plan')

    def _is_draft_submission(self) -> bool:
        return bool(getattr(self, 'save_draft', None) and self.save_draft.data)

    def validate(self, extra_validators=None):
        """Allow draft saves without completing required fields."""

        if not self._is_draft_submission():
            return super().validate(extra_validators=extra_validators)

        original_validators = {
            'title': self.title.validators,
            'description': self.description.validators,
            'price': self.price.validators,
        }
        try:
            self.title.validators = [Optional()]
            self.description.validators = [Optional()]
            self.price.validators = [Optional()]
            return super().validate(extra_validators=extra_validators)
        finally:
            self.title.validators = original_validators['title']
            self.description.validators = original_validators['description']
            self.price.validators = original_validators['price']

    def validate_category_ids(self, category_ids):
        # Only enforce category requirement on final save, not on draft save
        if self._is_draft_submission():
            return

        if not category_ids.data or len(category_ids.data) < 1:
            raise ValidationError('Please select at least one category for this plan.')

    def validate_sale_price(self, sale_price):
        """Prevent inconsistent price states.

        Sale price is optional, but if provided it must not exceed the base price.
        """
        if sale_price.data is None:
            return
        if getattr(self, 'price', None) is None or self.price.data is None:
            return
        try:
            if sale_price.data > self.price.data:
                raise ValidationError('Sale price must be less than or equal to the display price.')
        except TypeError:
            raise ValidationError('Invalid sale price value.')


class PowerfulPostForm(FlaskForm):
    """Admin form for creating/editing blog posts."""

    title = StringField('Article Title', validators=[DataRequired(), Length(max=200)])
    slug = StringField('Slug (optional)', validators=[Optional(), Length(max=200)])
    meta_title = StringField('Meta Title', validators=[Optional(), Length(max=150)])
    meta_description = TextAreaField('Meta Description', validators=[Optional(), Length(max=160)])
    content = CKEditorField('Content', validators=[DataRequired()])
    cover_image = FileField(
        'Cover Image',
        validators=[
            Optional(),
            FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], 'Images only.'),
        ],
    )
    plan_id = SelectField('Link this article to a plan', coerce=int, validators=[Optional()])
    status = SelectField(
        'Status',
        choices=[
            (BlogPost.STATUS_DRAFT, 'Draft'),
            (BlogPost.STATUS_PUBLISHED, 'Published'),
            (BlogPost.STATUS_ARCHIVED, 'Archived'),
        ],
        default=BlogPost.STATUS_DRAFT,
    )
    submit = SubmitField('Save Article')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        plans = HousePlan.query.order_by(HousePlan.title.asc()).all()
        choices = [(0, 'No linked plan')] + [(plan.id, f"#{plan.reference_code} — {plan.title}") for plan in plans]
        self.plan_id.choices = choices
    save_draft = SubmitField('Save Draft')

    def _is_draft_submission(self):
        return bool(getattr(self, 'save_draft', None) and self.save_draft.data)

    def validate(self, extra_validators=None):
        """Allow draft saves without completing required fields."""

        if not self._is_draft_submission():
            return super().validate(extra_validators=extra_validators)

        original_validators = {
            'title': self.title.validators,
            'content': self.content.validators,
        }
        try:
            self.title.validators = [Optional()]
            self.content.validators = [Optional()]
            return super().validate(extra_validators=extra_validators)
        finally:
            self.title.validators = original_validators['title']
            self.content.validators = original_validators['content']

    def validate_category_ids(self, category_ids):
        # Only enforce category requirement on final save, not on draft save
        # Check if this is a draft save by looking at the form data
        if hasattr(self, 'save_draft') and self.save_draft.data:
            # Draft save - categories optional
            return
        
        if not category_ids.data or len(category_ids.data) < 1:
            raise ValidationError('Please select at least one category for this plan.')

    def validate_sale_price(self, sale_price):
        """Prevent inconsistent price states.

        Sale price is optional, but if provided it must not exceed the base price.
        """
        if sale_price.data is None:
            return
        if self.price.data is None:
            return
        try:
            if sale_price.data > self.price.data:
                raise ValidationError('Sale price must be less than or equal to the display price.')
        except TypeError:
            raise ValidationError('Invalid sale price value.')


class CategoryForm(FlaskForm):
    """Form for creating/editing categories (Admin)"""
    
    name = StringField('Category Name', validators=[
        DataRequired(message='Name is required'),
        Length(max=100)
    ])
    description = TextAreaField('Description')
    submit = SubmitField('Save Category')

    def __init__(self, *args, category_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._category_id = category_id


class PlanFAQForm(FlaskForm):
    """Form for creating and editing plan-specific FAQ items."""

    question = StringField('Question', validators=[
        DataRequired(message='Question is required'),
        Length(max=500)
    ])
    answer = TextAreaField('Answer', validators=[
        DataRequired(message='Answer is required'),
        Length(max=8000)
    ])
    pack_context = SelectField('Pack context', choices=[('', 'All packs'), ('free', 'Free Pack'), ('pro', 'Pro Pack'), ('ultimate', 'Ultimate Pack')], validators=[Optional()])
    submit = SubmitField('Save FAQ')

    def validate_name(self, name):
        normalized = (name.data or '').strip()
        if not normalized:
            raise ValidationError('Category name is required.')

        query = Category.query.filter(Category.name.ilike(normalized))
        if self._category_id is not None:
            query = query.filter(Category.id != self._category_id)

        if query.first() is not None:
            raise ValidationError('This category name already exists. Please choose a different name.')


class SearchForm(FlaskForm):
    """Search form for filtering house plans"""
    
    query = StringField('Search', validators=[Length(max=200)])
    category = SelectField('Category', coerce=int)
    min_bedrooms = SelectField('Min Bedrooms', coerce=int, choices=[
        (0, 'Any'), (1, '1+'), (2, '2+'), (3, '3+'), (4, '4+'), (5, '5+')
    ])
    min_bathrooms = SelectField('Min Bathrooms', coerce=int, choices=[
        (0, 'Any'), (1, '1+'), (2, '2+'), (3, '3+'), (4, '4+')
    ])
    max_price = DecimalField('Max Price', validators=[Optional()])
    submit = SubmitField('Search')


class PasswordResetRequestForm(FlaskForm):
    """Form for requesting password reset"""
    
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address')
    ])
    submit = SubmitField('Request Password Reset')


class PasswordResetForm(FlaskForm):
    """Form for resetting password"""
    
    password = PasswordField('New Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=8, message='Password must be at least 8 characters')
    ])
    password_confirm = PasswordField('Confirm Password', validators=[
        DataRequired(message='Please confirm your password'),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Reset Password')
