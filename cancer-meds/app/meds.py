from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app as app
from flask_login import login_required, current_user
from .models import Medicine, User, Match
from . import db
from datetime import datetime
from . import mail
from flask_mail import Message
import os
from werkzeug.utils import secure_filename
from uuid import uuid4

meds_bp = Blueprint("meds", __name__, url_prefix="/meds", template_folder="templates")

from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DateField, SubmitField, HiddenField
from wtforms.validators import DataRequired, NumberRange


class ProfileForm(FlaskForm):
    name = StringField('Full name', validators=[DataRequired()])
    phone = StringField('Phone')
    latitude = HiddenField('Latitude')
    longitude = HiddenField('Longitude')
    submit = SubmitField('Save')

class MedicineForm(FlaskForm):
    name = StringField("Medicine Name", validators=[DataRequired()])
    quantity = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=1)])
    expiry_date = DateField("Expiry Date (optional)", format="%Y-%m-%d", validators=[])
    # location field is handled via request.form (optional)
    submit = SubmitField("Save")

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "pdf"}

def allowed_file(filename):
    if not filename:
        return False
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_uploads(files, medicine_id, uploader_id, image_type):
    uploads = []
    upload_dir = os.path.join(app.static_folder, 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    for f in files:
        if f and allowed_file(f.filename):
            filename = secure_filename(f.filename)
            unique = f"{uuid4().hex}_{filename}"
            dest = os.path.join(upload_dir, unique)
            f.save(dest)
            # store path relative to static folder
            relpath = f"uploads/{unique}"
            img = None
            try:
                from .models import Image
                img = Image(filename=relpath, medicine_id=medicine_id, uploader_id=uploader_id, image_type=image_type)
                db.session.add(img)
                uploads.append(img)
            except Exception as e:
                print("Error saving image record:", e)
    return uploads

def send_notification(to, subject, body):
    # Use Flask-Mail if configured, otherwise fallback to print
    try:
        if app.config.get("MAIL_SERVER"):
            msg = Message(subject=subject, recipients=[to], body=body)
            mail.send(msg)
        else:
            print("MAIL not configured. Notification to:", to, subject, body)
    except Exception as e:
        print("Error sending mail:", e)

@meds_bp.route("/my_donations")
@login_required
def my_donations():
    donations = Medicine.query.filter_by(user_id=current_user.id, type="donation").all()
    return render_template("donor/donations.html", donations=donations)

@meds_bp.route("/add_donation", methods=["GET","POST"])
@login_required
def add_donation():
    if current_user.role != "donor":
        flash("Only donors can add donations", "warning")
        return redirect(url_for("home"))
    form = MedicineForm()
    if form.validate_on_submit():
        location = request.form.get('location')
        # store donation; user coordinates are stored on the User model instead of per-medicine
        m = Medicine(user_id=current_user.id, name=form.name.data,
                     quantity=form.quantity.data, expiry_date=form.expiry_date.data,
                     type="donation", status="available", location=location)
        db.session.add(m)
        db.session.commit()
        # handle uploaded images
        files = request.files.getlist('images')
        if files:
            save_uploads(files, m.id, current_user.id, 'donation_photo')
            db.session.commit()
        flash("Donation added", "success")
        return redirect(url_for("meds.my_donations"))
    return render_template("donor/add_medicine.html", form=form)

@meds_bp.route("/edit_donation/<int:mid>", methods=["GET","POST"])
@login_required
def edit_donation(mid):
    m = Medicine.query.get_or_404(mid)
    if m.user_id != current_user.id:
        flash("Unauthorized", "danger"); return redirect(url_for("home"))
    if m.status == "matched":
        flash("Cannot edit matched item", "warning"); return redirect(url_for("meds.my_donations"))
    form = MedicineForm(obj=m)
    if form.validate_on_submit():
        m.name = form.name.data
        m.quantity = form.quantity.data
        m.expiry_date = form.expiry_date.data
        db.session.commit()
        flash("Updated", "success")
        return redirect(url_for("meds.my_donations"))
    return render_template("donor/edit_medicine.html", form=form, med=m)

@meds_bp.route("/delete_donation/<int:mid>", methods=["POST"])
@login_required
def delete_donation(mid):
    m = Medicine.query.get_or_404(mid)
    if m.user_id != current_user.id:
        flash("Unauthorized", "danger"); return redirect(url_for("home"))
    if m.status == "matched":
        flash("Cannot delete matched item", "warning"); return redirect(url_for("meds.my_donations"))
    db.session.delete(m); db.session.commit()
    flash("Deleted", "info")
    return redirect(url_for("meds.my_donations"))

# Requester equivalents
@meds_bp.route("/my_requests")
@login_required
def my_requests():
    reqs = Medicine.query.filter_by(user_id=current_user.id, type="request").all()
    return render_template("requester/requests.html", requests=reqs)

@meds_bp.route("/add_medicine", methods=["GET","POST"])
@login_required
def add_medicine():
    if current_user.role != "requester":
        flash("Only requesters can add requests", "warning")
        return redirect(url_for("home"))
    form = MedicineForm()
    if form.validate_on_submit():
        location = request.form.get('location')
        # store request; user coordinates are stored on the User model instead of per-medicine
        m = Medicine(user_id=current_user.id, name=form.name.data,
                     quantity=form.quantity.data, expiry_date=form.expiry_date.data,
                     type="request", status="available", location=location)
        db.session.add(m)
        db.session.commit()
        # handle prescription uploads
        files = request.files.getlist('prescriptions')
        if files:
            save_uploads(files, m.id, current_user.id, 'prescription')
            db.session.commit()
        flash("Request added", "success")
        return redirect(url_for("meds.my_requests"))
    return render_template("requester/add_request.html", form=form)

@meds_bp.route("/edit_request/<int:mid>", methods=["GET","POST"])
@login_required
def edit_request(mid):
    m = Medicine.query.get_or_404(mid)
    if m.user_id != current_user.id:
        flash("Unauthorized", "danger"); return redirect(url_for("home"))
    if m.status == "matched":
        flash("Cannot edit matched item", "warning"); return redirect(url_for("meds.my_requests"))
    form = MedicineForm(obj=m)
    if form.validate_on_submit():
        m.name = form.name.data
        m.quantity = form.quantity.data
        m.expiry_date = form.expiry_date.data
        db.session.commit()
        flash("Updated", "success")
        return redirect(url_for("meds.my_requests"))
    return render_template("requester/edit_request.html", form=form, med=m)

@meds_bp.route("/delete_request/<int:mid>", methods=["POST"])
@login_required
def delete_request(mid):
    m = Medicine.query.get_or_404(mid)
    if m.user_id != current_user.id:
        flash("Unauthorized", "danger"); return redirect(url_for("home"))
    if m.status == "matched":
        flash("Cannot delete matched item", "warning"); return redirect(url_for("meds.my_requests"))
    db.session.delete(m); db.session.commit()
    flash("Deleted", "info")
    return redirect(url_for("meds.my_requests"))


# Profile page to set user contact info and coordinates
@meds_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    if form.validate_on_submit():
        # update basic info
        current_user.name = form.name.data
        current_user.phone = form.phone.data
        # coords (optional)
        lat = form.latitude.data
        lon = form.longitude.data
        try:
            current_user.latitude = float(lat) if lat not in (None, '', 'null') else None
        except Exception:
            current_user.latitude = None
        try:
            current_user.longitude = float(lon) if lon not in (None, '', 'null') else None
        except Exception:
            current_user.longitude = None
        db.session.add(current_user)
        db.session.commit()
        flash('Profile updated', 'success')
        return redirect(url_for('meds.profile'))

    # prefill the form with current values
    if request.method == 'GET':
        form.name.data = current_user.name
        form.phone.data = current_user.phone
        form.latitude.data = getattr(current_user, 'latitude', '') or ''
        form.longitude.data = getattr(current_user, 'longitude', '') or ''

    return render_template('profile.html', form=form)