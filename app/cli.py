import click
from flask.cli import with_appcontext

from app.extensions import db
from app.models import User, Category, HousePlan


@click.command('create-admin')
@click.option('--username', prompt=True, help='Admin username')
@click.option(
    '--password',
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help='Admin password (will not be echoed)'
)
@with_appcontext
def create_admin_command(username: str, password: str) -> None:
    """Create (or update) an admin user."""
    import os

    username = (username or '').strip()

    if not username:
        raise click.ClickException('Username is required.')

    existing_by_username = User.query.filter_by(username=username).first()

    admin_email = (os.getenv('ADMIN_EMAIL') or username).strip()

    user = existing_by_username
    if user is None:
        user = User(username=username, email=admin_email, role='superadmin', is_active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Created admin user '{user.username}'.")
        return

    # Update path
    user.username = username
    user.email = admin_email
    user.role = 'superadmin'
    user.is_active = True
    user.set_password(password)
    db.session.commit()
    click.echo(f"Updated admin user '{user.username}'.")


@click.command('reset-admin-password')
@click.option('--username', default=None, help='Admin username (defaults to ADMIN_USERNAME env var)')
@with_appcontext
def reset_admin_password_command(username: str) -> None:
    """Reset admin password from environment variable ADMIN_PASSWORD or prompt."""
    import os

    username = (username or os.getenv('ADMIN_USERNAME') or 'bacseried@gmail.com').strip()
    admin_email = (os.getenv('ADMIN_EMAIL') or username).strip()
    
    user = User.query.filter_by(username=username).first()

    # Try to get password from environment variable first
    password = os.getenv('ADMIN_PASSWORD')

    if not password:
        # If running non-interactively (CI), default to environment value only
        try:
            password = click.prompt('New password', hide_input=True, confirmation_prompt=True)
        except Exception:
            raise click.ClickException('ADMIN_PASSWORD is required when running non-interactively')

    if not user:
        # Create user if missing to ensure release commands are idempotent
        user = User(username=username, email=admin_email, role='superadmin', is_active=True)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Created and updated admin user '{user.username}'.")
        return

    # Update existing user
    user.set_password(password)
    user.email = admin_email
    user.role = 'superadmin'
    user.is_active = True
    db.session.commit()

    click.echo(f"✓ Password updated for user '{user.username}'")
    click.echo(f"✓ Admin status: {user.is_admin}")
    click.echo(f"✓ Active status: {user.is_active}")


@click.command('seed-categories')
@with_appcontext
def seed_categories_command() -> None:
    """Seed default categories into the database."""
    categories = [
        {'name': 'Modern', 'slug': 'modern', 'description': 'Contemporary designs with clean lines'},
        {'name': 'Traditional', 'slug': 'traditional', 'description': 'Classic architectural styles'},
        {'name': 'Bungalow', 'slug': 'bungalow', 'description': 'Single-story cozy homes'},
        {'name': 'Two-Story', 'slug': 'two-story', 'description': 'Multi-level residential designs'},
        {'name': 'Farmhouse', 'slug': 'farmhouse', 'description': 'Rustic and welcoming country homes'},
        {'name': 'Cottage', 'slug': 'cottage', 'description': 'Small charming vacation homes'},
        {'name': 'Luxury', 'slug': 'luxury', 'description': 'High-end premium designs'},
    ]
    
    created_count = 0
    for cat_data in categories:
        existing = Category.query.filter_by(slug=cat_data['slug']).first()
        if not existing:
            category = Category(
                name=cat_data['name'],
                slug=cat_data['slug'],
                description=cat_data['description']
            )
            db.session.add(category)
            created_count += 1
    
    db.session.commit()
    click.echo(f"Seeded {created_count} categories. Total categories: {Category.query.count()}")


@click.command('seed-sample-plans')
@with_appcontext
def seed_sample_plans_command() -> None:
    """Seed sample house plans into the database."""
    # Ensure we have at least one category
    category = Category.query.first()
    if not category:
        click.echo("No categories found. Run 'flask seed-categories' first.")
        return
    
    sample_plans = [
        {
            'title': 'Modern 3-Bedroom Family Home',
            'short_description': 'Contemporary design with open-plan living',
            'description': 'A beautiful modern family home featuring an open-plan kitchen and living area, three spacious bedrooms, and a stylish outdoor entertaining space.',
            'bedrooms': 3,
            'bathrooms': 2,
            'stories': 1,
            'garage': 2,
            'total_area_sqft': 1850,
            'total_area_m2': 171.9,
            'price': 299.00,
            'is_published': True,
        },
        {
            'title': 'Compact 2-Bedroom Starter Home',
            'short_description': 'Perfect for first-time buyers or downsizers',
            'description': 'An efficient and well-designed 2-bedroom home with modern amenities, ideal for couples or small families.',
            'bedrooms': 2,
            'bathrooms': 1,
            'stories': 1,
            'garage': 1,
            'total_area_sqft': 1100,
            'total_area_m2': 102.2,
            'price': 199.00,
            'is_published': True,
        },
        {
            'title': 'Spacious 4-Bedroom Two-Story',
            'short_description': 'Large family home with study',
            'description': 'A generous two-story home with four bedrooms, home office, and multiple living areas perfect for growing families.',
            'bedrooms': 4,
            'bathrooms': 2.5,
            'stories': 2,
            'garage': 2,
            'total_area_sqft': 2650,
            'total_area_m2': 246.2,
            'price': 399.00,
            'is_published': True,
            'is_featured': True,
        },
    ]
    
    created_count = 0
    for plan_data in sample_plans:
        # Check if plan with same title exists
        existing = HousePlan.query.filter_by(title=plan_data['title']).first()
        if not existing:
            plan = HousePlan(**plan_data)
            plan.categories = [category]
            # Set computed fields
            plan.number_of_bedrooms = plan_data['bedrooms']
            plan.number_of_bathrooms = plan_data['bathrooms']
            plan.number_of_floors = plan_data['stories']
            plan.square_feet = int(plan_data['total_area_sqft'])
            
            db.session.add(plan)
            created_count += 1
    
    db.session.commit()
    click.echo(f"Seeded {created_count} sample plans. Total plans: {HousePlan.query.count()}")

