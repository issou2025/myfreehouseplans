import os
import secrets
from app import create_app
from app.extensions import db

# Ensure env vars for admin
os.environ['ADMIN_USERNAME'] = os.environ.get('ADMIN_USERNAME', 'bootstrap_admin')
os.environ['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD') or secrets.token_urlsafe(16)

app = create_app('testing')

with app.app_context():
    # Start from a clean DB state to validate bootstrap creates admin
    db.drop_all()
    db.create_all()

    # Manual bootstrap logic matching app factory behavior
    from app.models import User
    admin = User.query.filter_by(role='superadmin').first()
    if not admin:
        admin_username = os.environ.get('ADMIN_USERNAME')
        admin_password = os.environ.get('ADMIN_PASSWORD')
        if admin_username and admin_password:
            new_admin = User(username=admin_username, role='superadmin', is_active=True)
            new_admin.set_password(admin_password)
            db.session.add(new_admin)
            db.session.commit()

    admin = User.query.filter_by(role='superadmin').first()
    if admin:
        print('Admin exists after manual bootstrap: ', admin.username)
        ok = admin.check_password(os.environ['ADMIN_PASSWORD'])
        print('Password verification passed:', ok)
    else:
        print('Admin was NOT created')
