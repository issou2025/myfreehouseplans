from app import create_app

app = create_app()
with app.app_context():
    from app.models import User
    u = User.query.filter_by(username='admin').first()
    if u:
        print('FOUND', u.username, 'role=', u.role, 'is_admin=', u.is_admin)
    else:
        print('NOT_FOUND')
