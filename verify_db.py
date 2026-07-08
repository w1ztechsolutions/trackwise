from app import create_app
from app.models import db, User

app = create_app()
print(app.config['SQLALCHEMY_DATABASE_URI'])
with app.app_context():
    print('db ok')
    dialect = db.engine.dialect.name
    if dialect == 'sqlite':
        result = db.session.execute(db.text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")).scalar()
        print('users table exists:', result is not None)
    else:
        print('users table exists:', db.session.execute(db.text("SELECT to_regclass('users')")).scalar())
    print('user count:', db.session.query(User).count())
