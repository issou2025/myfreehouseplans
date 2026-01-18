from app import app, db
with app.app_context():
    try:
        db.create_all()
        print('--- SUCCESS: Database tables synchronized. Existing data preserved. ---')
    except Exception as e:
        print(f'--- ERROR: {e} ---')