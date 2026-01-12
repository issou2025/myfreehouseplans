from app import create_app
from app.extensions import db
import os
import secrets

os.environ['ADMIN_USERNAME'] = os.environ.get('ADMIN_USERNAME', 'bootstrap_admin')
os.environ['ADMIN_PASSWORD'] = os.environ.get('ADMIN_PASSWORD') or secrets.token_urlsafe(16)
app = create_app('testing')
with app.app_context():
    from app.models import User
    u = User.query.filter_by(role='superadmin').first()
    if u:
        print('stored password_hash repr:', repr(u.password_hash))
        print('check_password:', u.check_password(os.environ['ADMIN_PASSWORD']))
    else:
        print('no admin')
