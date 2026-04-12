from app import create_app
from app.models.user import User
app = create_app()
with app.app_context():
    count = User.query.count()
    print(f"Total Users: {count}")
    user = User.query.filter_by(email="dr.mehta@vitalmind.com").first()
    print(f"Dr. Mehta found: {user is not None}")
