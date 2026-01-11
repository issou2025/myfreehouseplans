from app import create_app
from app.extensions import db

app = create_app('testing')

with app.app_context():
    # Ensure tables are created for testing
    db.create_all()

    client = app.test_client()

    data = {
        'name': 'Test User',
        'email': 'test@example.com',
        'phone': '+10000000000',
        'subject': 'Test message',
        'inquiry_type': 'support',
        'message': 'This is an automated test message from test_contact script.',
        'subscribe': 'y'
    }

    resp = client.post('/contact', data=data, follow_redirects=True)
    print('Status code:', resp.status_code)
    body = resp.get_data(as_text=True)
    # Check for success confirmation text
    found = 'Thank you! Your message has been sent. We will get back to you shortly.' in body
    print('Confirmation present in response body:', found)

    # Verify DB entry
    from app.models import ContactMessage
    msg = ContactMessage.query.order_by(ContactMessage.created_at.desc()).first()
    if msg:
        print('Saved message ID:', msg.id)
        print('Saved message email:', msg.email)
    else:
        print('No message found in DB')
