from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from .models import Medicine, User, Match
from . import db
from datetime import datetime
from . import mail
from flask_mail import Message
from flask import current_app as app

meds_bp = Blueprint("meds", __name__, url_prefix="/meds", template_folder="templates")

from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DateField, SubmitField, HiddenField
from wtforms.validators import DataRequired, NumberRange

class MedicineForm(FlaskForm):
    name = StringField("Medicine Name", validators=[DataRequired()])
    quantity = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=1)])
    expiry_date = DateField("Expiry Date (optional)", format="%Y-%m-%d", validators=[])
    submit = SubmitField("Save")

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
        m = Medicine(user_id=current_user.id, name=form.name.data,
                     quantity=form.quantity.data, expiry_date=form.expiry_date.data,
                     type="donation", status="available")
        db.session.add(m)
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
        m = Medicine(user_id=current_user.id, name=form.name.data,
                     quantity=form.quantity.data, expiry_date=form.expiry_date.data,
                     type="request", status="available")
        db.session.add(m)
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