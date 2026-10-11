import json
import os

from app.auth.service import passwords
from app.db import SessionLocal
from app.local_paths import STATE_ROOT
from app.models import Library, Shelf, User
from sqlalchemy import select

credentials = (
    {"admin_email": os.environ["ADMIN_EMAIL"], "admin_password": os.environ["ADMIN_PASSWORD"]}
    if os.environ.get("ADMIN_EMAIL") and os.environ.get("ADMIN_PASSWORD")
    else json.loads((STATE_ROOT / "credentials.json").read_text())
)
with SessionLocal() as db:
    user = db.scalar(select(User).where(User.email == credentials["admin_email"]))
    if not user:
        user = User(
            email=credentials["admin_email"],
            name="オーナー",
            password_hash=passwords.hash(credentials["admin_password"]),
        )
        db.add(user)
        db.flush()
        library = Library(owner_id=user.id)
        db.add(library)
        db.flush()
        db.add_all(
            [
                Shelf(library_id=library.id, name="日々の記録", color="#4f7bff"),
                Shelf(library_id=library.id, name="アイデア", color="#b08ad8"),
            ]
        )
        db.commit()
        print("Owner account created. Use the private credentials generated during setup.")
    else:
        print("Local owner already exists; credentials unchanged.")
