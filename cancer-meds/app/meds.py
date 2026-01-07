from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app as app, make_response
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

def no_cache(f):
    """Decorator to prevent caching of responses"""
    def decorated_function(*args, **kwargs):
        response = make_response(f(*args, **kwargs))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    decorated_function.__name__ = f.__name__
    return decorated_function


class ProfileForm(FlaskForm):
    name = StringField('Full name', validators=[DataRequired()])
    phone = StringField('Phone')
    latitude = HiddenField('Latitude')
    longitude = HiddenField('Longitude')
    submit = SubmitField('Save')

class MedicineForm(FlaskForm):
    name = StringField("Medicine Name", validators=[DataRequired()])
    quantity = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=1)])
    expiry_date = DateField("Expiry Date", format="%Y-%m-%d", validators=[DataRequired()])
    # location field is handled via request.form (mandatory)
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
        location = request.form.get('location', '').strip()
        # validate location is not empty
        if not location:
            flash("Location is required", "danger")
            return render_template("donor/add_medicine.html", form=form)
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
@no_cache
def edit_donation(mid):
    m = Medicine.query.get_or_404(mid)
    if m.user_id != current_user.id:
        flash("Unauthorized", "danger"); return redirect(url_for("home"))
    if m.status == "matched":
        flash("Cannot edit matched item", "warning"); return redirect(url_for("meds.my_donations"))
    
    form = MedicineForm()
    
    if request.method == "POST":
        print(f"DEBUG: POST request received for edit_donation {mid}")
        print(f"DEBUG: Form data - name: {request.form.get('name')}, quantity: {request.form.get('quantity')}, expiry: {request.form.get('expiry_date')}")
        
        # Update medicine data
        m.name = request.form.get('name', m.name).strip()
        m.quantity = request.form.get('quantity', m.quantity)
        expiry_str = request.form.get('expiry_date')
        if expiry_str:
            try:
                m.expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
            except:
                pass
        
        # Handle image deletions (marked with checkboxes)
        delete_image_ids = request.form.getlist('delete_images')
        if delete_image_ids:
            from .models import Image
            for img_id in delete_image_ids:
                img = Image.query.get(img_id)
                if img and img.medicine_id == mid:
                    # Delete file from disk
                    try:
                        filepath = os.path.join(app.static_folder, img.filename)
                        if os.path.exists(filepath):
                            os.remove(filepath)
                    except Exception as e:
                        print(f"Error deleting file: {e}")
                    # Delete database record
                    db.session.delete(img)
            print(f"DEBUG: Deleted {len(delete_image_ids)} images")
        
        # Handle new image uploads
        files = request.files.getlist('images')
        files = [f for f in files if f and f.filename]
        if files:
            print(f"DEBUG: Uploading {len(files)} images")
            save_uploads(files, mid, current_user.id, 'medicine')
        else:
            print("DEBUG: No images selected")
        
        db.session.commit()
        flash("Updated successfully", "success")
        response = make_response(redirect(url_for("meds.edit_donation", mid=mid)))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
    
    return render_template("donor/edit_medicine.html", form=form, med=m)

@meds_bp.route("/delete_donation/<int:mid>", methods=["POST"])
@login_required
def delete_donation(mid):
    m = Medicine.query.get_or_404(mid)
    if m.user_id != current_user.id:
        flash("Unauthorized", "danger"); return redirect(url_for("home"))
    if m.status == "matched":
        flash("Cannot delete matched item", "warning"); return redirect(url_for("meds.my_donations"))
    # Delete associated images first
    from .models import Image
    Image.query.filter_by(medicine_id=mid).delete()
    db.session.delete(m)
    db.session.commit()
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
        location = request.form.get('location', '').strip()
        # validate location is not empty
        if not location:
            flash("Location is required", "danger")
            return render_template("requester/add_request.html", form=form)
        # validate prescriptions are uploaded
        files = request.files.getlist('prescriptions')
        if not files or all(f.filename == '' for f in files):
            flash("At least one prescription file is required", "danger")
            return render_template("requester/add_request.html", form=form)
        # store request; user coordinates are stored on the User model instead of per-medicine
        m = Medicine(user_id=current_user.id, name=form.name.data,
                     quantity=form.quantity.data, expiry_date=form.expiry_date.data,
                     type="request", status="available", location=location)
        db.session.add(m)
        db.session.commit()
        # handle prescription uploads
        if files:
            save_uploads(files, m.id, current_user.id, 'prescription')
            db.session.commit()
        flash("Request added", "success")
        return redirect(url_for("meds.my_requests"))
    return render_template("requester/add_request.html", form=form)

@meds_bp.route("/edit_request/<int:mid>", methods=["GET","POST"])
@login_required
@no_cache
def edit_request(mid):
    m = Medicine.query.get_or_404(mid)
    if m.user_id != current_user.id:
        flash("Unauthorized", "danger"); return redirect(url_for("home"))
    if m.status == "matched":
        flash("Cannot edit matched item", "warning"); return redirect(url_for("meds.my_requests"))
    
    form = MedicineForm()
    
    if request.method == "POST":
        print(f"DEBUG: POST request received for edit_request {mid}")
        print(f"DEBUG: Form data - name: {request.form.get('name')}, quantity: {request.form.get('quantity')}, expiry: {request.form.get('expiry_date')}")
        
        # Update medicine data
        m.name = request.form.get('name', m.name).strip()
        m.quantity = request.form.get('quantity', m.quantity)
        expiry_str = request.form.get('expiry_date')
        if expiry_str:
            try:
                m.expiry_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
            except:
                pass
        
        # Handle prescription deletions (marked with checkboxes)
        delete_image_ids = request.form.getlist('delete_images')
        if delete_image_ids:
            from .models import Image
            for img_id in delete_image_ids:
                img = Image.query.get(img_id)
                if img and img.medicine_id == mid:
                    # Delete file from disk
                    try:
                        filepath = os.path.join(app.static_folder, img.filename)
                        if os.path.exists(filepath):
                            os.remove(filepath)
                    except Exception as e:
                        print(f"Error deleting file: {e}")
                    # Delete database record
                    db.session.delete(img)
            print(f"DEBUG: Deleted {len(delete_image_ids)} prescriptions")
        
        # Handle new prescription uploads
        files = request.files.getlist('prescriptions')
        files = [f for f in files if f and f.filename]
        if files:
            print(f"DEBUG: Uploading {len(files)} prescriptions")
            save_uploads(files, mid, current_user.id, 'prescription')
        else:
            print("DEBUG: No prescriptions selected")
        
        db.session.commit()
        flash("Updated successfully", "success")
        response = make_response(redirect(url_for("meds.edit_request", mid=mid)))
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
    
    return render_template("requester/edit_request.html", form=form, req=m)

@meds_bp.route("/delete_request/<int:mid>", methods=["POST"])
@login_required
def delete_request(mid):
    m = Medicine.query.get_or_404(mid)
    if m.user_id != current_user.id:
        flash("Unauthorized", "danger"); return redirect(url_for("home"))
    if m.status == "matched":
        flash("Cannot delete matched item", "warning"); return redirect(url_for("meds.my_requests"))
    # Delete associated images first
    from .models import Image
    Image.query.filter_by(medicine_id=mid).delete()
    db.session.delete(m)
    db.session.commit()
    flash("Deleted", "info")
    return redirect(url_for("meds.my_requests"))


# Delete individual image
@meds_bp.route("/delete_image/<int:image_id>", methods=["POST"])
@login_required
@no_cache
def delete_image(image_id):
    from .models import Image
    img = Image.query.get_or_404(image_id)
    med = img.medicine
    
    # Verify ownership
    if med.user_id != current_user.id:
        flash("Unauthorized", "danger")
        return redirect(url_for("home"))
    
    # Delete the file from disk
    import os
    try:
        filepath = os.path.join(app.static_folder, img.filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        print(f"Error deleting file: {e}")
    
    # Delete the database record
    db.session.delete(img)
    db.session.commit()
    flash("Image deleted", "success")
    
    # Redirect back to edit form with no-cache headers
    if med.type == "donation":
        response = make_response(redirect(url_for("meds.edit_donation", mid=med.id)))
    else:
        response = make_response(redirect(url_for("meds.edit_request", mid=med.id)))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response


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