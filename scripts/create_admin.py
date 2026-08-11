from getpass import getpass

from app import create_app
from app.extensions import db
from app.models import Role, User
from app.security import hash_password


def main():
    app = create_app()
    with app.app_context():
        print("Create admin account")
        full_name = input("Full name: ").strip()
        email = input("Email: ").strip().lower()
        password = getpass("Password: ")

        existing = db.session.query(User).filter_by(email=email).first()
        if existing:
            existing.full_name = full_name or existing.full_name
            existing.password_hash = hash_password(password) if password else existing.password_hash
            existing.role = Role.ADMIN
            existing.is_email_verified = True
            db.session.commit()
            print("Updated existing user to ADMIN.")
            return

        u = User(
            full_name=full_name,
            email=email,
            password_hash=hash_password(password),
            role=Role.ADMIN,
            is_email_verified=True,
        )
        db.session.add(u)
        db.session.commit()
        print("Admin created.")


if __name__ == "__main__":
    main()

