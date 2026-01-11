from app import create_app
from app.extensions import db
import os
os.environ['ADMIN_USERNAME']='bootstrap_admin'
os.environ['ADMIN_PASSWORD']='ChangeMe123!'
app = create_app('testing')
with app.app_context():
    from app.models import User
    u = User.query.filter_by(role='superadmin').first()
    if u:
        print('stored pwd repr:', repr(u.password))
        print('check_password:', u.check_password('ChangeMe123!'))
    else:
        print('no admin')
