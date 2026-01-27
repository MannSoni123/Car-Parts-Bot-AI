from datetime import datetime,timezone
from .extensions import db
# from app import db 
class TimestampMixin:
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

class Lead(db.Model, TimestampMixin):
    __tablename__ = "leads"

    id = db.Column(db.Integer, primary_key=True)
    whatsapp_user_id = db.Column(db.String(64), index=True, nullable=False)
    user_locale = db.Column(db.String(16), nullable=True)
    intent = db.Column(db.String(64), nullable=True)
    query_text = db.Column(db.Text, nullable=True)
    assigned_agent = db.Column(db.String(128), nullable=True)
    status = db.Column(db.String(32), default="new", nullable=False)

class Stock(db.Model):
    __tablename__ = 'stock'

    id = db.Column(db.Integer, primary_key=True)
    tag = db.Column(db.String(500))
    brand_part_no = db.Column(db.String(255))     # ✔ cleaner than Text
    item_desc = db.Column(db.Text)
    price = db.Column(db.Float)                   # ✔ easier to use in python
    qty = db.Column(db.Integer)
    part_number = db.Column(db.String(255))
    brand = db.Column(db.String(255))
    unique_value = db.Column(db.Text)


 # or wherever your SQLAlchemy instance is

class IntentPrompt(db.Model):
    __tablename__ = "intent_prompts"
    id = db.Column(db.Integer, primary_key=True)
    # machine-safe
    intent_key = db.Column(db.String(100), unique=True, nullable=False)
    # human-friendly
    display_name = db.Column(db.String(255), nullable=False)
    prompt_text = db.Column(db.Text, nullable=False)
    intent_type = db.Column(
        db.String(20),
        nullable=False,
        server_default="text"   # 👈 VERY IMPORTANT
    )
    # uploaded file path (PDF/TXT)
    reference_file = db.Column(db.String(255), nullable=True)
    # extracted text from file (cached)
    reference_text = db.Column(db.Text, nullable=True)
    # Normalization rules for entity extraction
    parts_alias_text = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    # The unique WhatsApp ID (e.g., "919876543210")
    whatsapp_id = db.Column(db.String(50), unique=True, nullable=False)
    # The saved VIN for this user
    current_vin = db.Column(db.String(20), nullable=True)
 
    def __repr__(self):
        return f'<User {self.whatsapp_id}>'
