from . import db, login_manager
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(30))
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default="requester")  # donor or requester
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # optional precise user coordinates (for showing nearby matches)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    medicines = db.relationship("Medicine", backref="owner", lazy=True)
    sent_matches = db.relationship("Match", foreign_keys="Match.donor_id", backref="donor", lazy=True)
    received_matches = db.relationship("Match", foreign_keys="Match.requester_id", backref="requester", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    expiry_date = db.Column(db.Date, nullable=True)
    type = db.Column(db.String(20), nullable=False)  # 'donation' or 'request'
    status = db.Column(db.String(20), default="available")  # available, pending, matched, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    # optional proof file path (extend for uploads)
    proof = db.Column(db.String(300), nullable=True)
    # free-form location (address or GPS string)
    location = db.Column(db.String(300), nullable=True)



class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(300), nullable=False)
    medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.id', ondelete='CASCADE'), nullable=False)
    uploader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_type = db.Column(db.String(50), nullable=False)  # 'donation_photo' or 'prescription'
    approved = db.Column(db.Boolean, default=False)
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # relationships
    uploader = db.relationship('User', foreign_keys=[uploader_id], backref='uploaded_images')

# add reverse relationship on Medicine
Medicine.images = db.relationship('Image', backref='medicine', lazy=True)

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    donor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    donor_medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.id'), nullable=False)
    requester_medicine_id = db.Column(db.Integer, db.ForeignKey('medicine.id'), nullable=False)
    status = db.Column(db.String(20), default="pending")  # pending, donor_accepted, requester_confirmed, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    donor_medicine = db.relationship("Medicine", foreign_keys=[donor_medicine_id], uselist=False)
    requester_medicine = db.relationship("Medicine", foreign_keys=[requester_medicine_id], uselist=False)