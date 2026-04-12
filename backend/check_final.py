from app import create_app
from app.models.user import User
import os
app = create_app()
with app.app_context():
    print(f"URL: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
    print(f"Total Users: {User.query.count()}")
    u = User.query.filter_by(email='dr.mehta@vitalmind.com').first()
    print(f"Mehta: {u.first_name if u else 'None'}")
