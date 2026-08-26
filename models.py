from datetime import datetime
from extension import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    image = db.Column(db.Text, nullable=True)
    fullname = db.Column(db.String(128))
    email = db.Column(db.String(128), nullable=False, unique=True)
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="Customer")
    status = db.Column(db.String(30), nullable=False, default="Active")
    create_at = db.Column(db.DateTime, default=datetime.utcnow)
    update_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        if not self.password:
            return False
        try:
            return check_password_hash(self.password, raw_password)
        except Exception:
            return self.password == raw_password

