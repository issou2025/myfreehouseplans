"""
WTForms Form Classes for MyFreeHousePlans Application

This module defines all forms used throughout the application
for user input validation and CSRF protection.
"""

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, TextAreaField, DecimalField, IntegerField, FloatField, SelectField, SelectMultipleField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional, NumberRange, URL
from app.models import User, Category, ContactMessage
from app.models import PlanFAQ


class LoginForm(FlaskForm):
    """User login form"""
    
    username = StringField('Username', validators=[
        DataRequired(message='Username is required'),
        Length(max=80, message='Must be 80 characters or less')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required')
    ])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Log In')


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
    
    submit = SubmitField('Save Plan')
    save_draft = SubmitField('Save Draft')

    def validate_category_ids(self, category_ids):
        if not category_ids.data or len(category_ids.data) < 1:
            raise ValidationError('Please select at least one category for this plan.')


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
