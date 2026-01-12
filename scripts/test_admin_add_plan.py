from app import create_app
from app.extensions import db
import secrets


def run():
    app = create_app('testing')
    # Disable CSRF for testing client
    app.config['WTF_CSRF_ENABLED'] = False

    with app.app_context():
        # Fresh DB
        db.drop_all()
        db.create_all()

        # Create a category required by the form
        from app.models import Category, User
        cat = Category(name='Test Category')
        db.session.add(cat)
        db.session.commit()

        # Create admin user
        test_password = secrets.token_urlsafe(16)
        admin = User(username='admin', role='superadmin', is_active=True)
        admin.set_password(test_password)
        db.session.add(admin)
        db.session.commit()

        client = app.test_client()

        # Login
        rv = client.post('/admin/login', data={'username': 'admin', 'password': test_password}, follow_redirects=True)
        print('Login status:', rv.status_code)
        if b'Welcome back' not in rv.data:
            print('Login did not report welcome; response snippet:', rv.data[:300])

        # Access add-plan page
        rv = client.get('/admin/plans/add')
        print('/admin/plans/add status:', rv.status_code)

        # Post a minimal plan
        data = {
            'title': 'Automated Test Plan',
            'description': 'This is a test plan created by automated test.',
            'short_description': 'Short description',
            'price': '100.00',
            'price_pack_1': '0',
            'category_ids': [str(cat.id)],
            'is_published': 'y',
        }
        rv = client.post('/admin/plans/add', data=data, follow_redirects=True)
        print('Add plan status:', rv.status_code)
        if b'has been added successfully' in rv.data:
            print('Plan creation reported success')
        else:
            print('Plan creation response snippet:', rv.data[:400])


if __name__ == '__main__':
    run()
