from flask import Blueprint, render_template, redirect, url_for, flash, request
from app import db
from app.models import User
from flask_login import login_user, logout_user, login_required, current_user

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    role = request.args.get("role", None)  # donor or requester

    if not role:
        flash("Please choose donor or requester from home page.", "warning")
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash("Email already registered. Please login.", "danger")
            return redirect(url_for("auth.login"))

        user = User(name=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        print(f"✅ User added: {username}, {email}, {role}")
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html", role=role)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Login successful!", "success")
            if user.role == "donor":
                return redirect(url_for("auth.donor_dashboard"))
            else:
                return redirect(url_for("auth.requester_dashboard"))
        else:
            flash("Invalid credentials", "danger")

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))


@auth_bp.route("/donor_dashboard")
@login_required
def donor_dashboard():
    if current_user.role != "donor":
        flash("Unauthorized access", "danger")
        return redirect(url_for("auth.login"))
    return render_template("donor_dashboard.html", user=current_user)


@auth_bp.route("/requester_dashboard")
@login_required
def requester_dashboard():
    if current_user.role != "requester":
        flash("Unauthorized access", "danger")
        return redirect(url_for("auth.login"))
    # Provide medicines for the template
    from app.models import Medicine
    medicines = Medicine.query.filter_by(user_id=current_user.id, type="request").all()
    return render_template("requester_dashboard.html", user=current_user, medicines=medicines)
