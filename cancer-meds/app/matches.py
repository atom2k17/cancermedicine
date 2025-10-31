from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app as app
from flask_login import login_required, current_user
from .models import Medicine, Match, User
from datetime import datetime
from . import db, mail
from flask_mail import Message
import math

matches_bp = Blueprint("matches", __name__, url_prefix="/matches", template_folder="templates")


def send_notification(to, subject, body):
    try:
        if app.config.get("MAIL_SERVER"):
            msg = Message(subject=subject, recipients=[to], body=body)
            mail.send(msg)
        else:
            print("MAIL not configured. Notification to:", to, subject, body)
    except Exception as e:
        print("Error sending mail:", e)

@matches_bp.route("/my_matches")
@login_required
def my_matches():
    matches = []
    if current_user.role == "donor":
        matches = Match.query.filter_by(donor_id=current_user.id).order_by(Match.created_at.desc()).all()
    elif current_user.role == "requester":
        matches = Match.query.filter_by(requester_id=current_user.id).order_by(Match.created_at.desc()).all()
    # compute distance (km) for each match if coordinates are available
    def haversine_km(lat1, lon1, lat2, lon2):
        if None in (lat1, lon1, lat2, lon2):
            return None
        R = 6371.0
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    for m in matches:
        try:
            # use user coordinates (donor/requester) rather than per-medicine coordinates
            dlat = getattr(m.donor, 'latitude', None)
            dlon = getattr(m.donor, 'longitude', None)
            rlat = getattr(m.requester, 'latitude', None)
            rlon = getattr(m.requester, 'longitude', None)
            dist = haversine_km(dlat, dlon, rlat, rlon)
            m.distance_km = round(dist, 1) if dist is not None else None
        except Exception:
            m.distance_km = None

    return render_template("matches/my_matches.html", matches=matches)


@matches_bp.route('/pending_verifications')
@login_required
def pending_verifications():
    if current_user.role != 'doctor':
        flash('Unauthorized', 'danger'); return redirect(url_for('home'))
    # show matches that are awaiting verification
    pending = Match.query.filter_by(status='awaiting_verification').order_by(Match.created_at.desc()).all()

    # also show matches/images this doctor has already approved
    from .models import Image
    approved_imgs = Image.query.filter_by(approved=True, approved_by=current_user.id).all()
    approved_matches_set = set()
    for img in approved_imgs:
        # find matches where this image's medicine is either donor or requester medicine
        m = Match.query.filter((Match.donor_medicine_id == img.medicine_id) | (Match.requester_medicine_id == img.medicine_id)).first()
        if m:
            approved_matches_set.add(m)
    approved = sorted(list(approved_matches_set), key=lambda x: x.created_at, reverse=True)

    return render_template('matches/pending_verifications.html', pending=pending, approved=approved)

@matches_bp.route("/find")
@login_required
def find_matches():
    # Very simple matching UI: requester searches donations by name
    query = request.args.get("q", "")
    donations = []
    if query:
        donations = Medicine.query.filter(Medicine.type=="donation",
                                          Medicine.status=="available",
                                          Medicine.name.ilike(f"%{query}%")).all()
    # If requester, provide their available requests for matching
    requests = []
    if current_user.is_authenticated and getattr(current_user, 'role', None) == 'requester':
        requests = Medicine.query.filter_by(user_id=current_user.id, type="request", status="available").all()
    return render_template("matches/matches.html", donations=donations, query=query, requests=requests)

@matches_bp.route("/request_match/<int:donor_mid>/<int:request_mid>", methods=["POST"])
@login_required
def request_match(donor_mid, request_mid):
    donor_med = Medicine.query.get_or_404(donor_mid)
    req_med = Medicine.query.get_or_404(request_mid)

    # basic checks
    if donor_med.type != "donation" or req_med.type != "request":
        flash("Invalid types", "danger"); return redirect(url_for("matches.find_matches"))

    if donor_med.status != "available" or req_med.status != "available":
        flash("One of the items already matched", "warning"); return redirect(url_for("matches.find_matches"))

    # create match with requester as current_user if they own the request
    if req_med.user_id != current_user.id:
        flash("You must initiate match from your request", "danger"); return redirect(url_for("matches.find_matches"))

    match = Match(donor_id=donor_med.user_id,
                  requester_id=req_med.user_id,
                  donor_medicine_id=donor_med.id,
                  requester_medicine_id=req_med.id,
                  status="pending")
    db.session.add(match)
    # mark as pending to prevent other matches
    donor_med.status = "pending"
    req_med.status = "pending"
    db.session.commit()

    # notify donor
    donor_user = User.query.get(donor_med.user_id)
    send_notification(donor_user.email,
                      "New request for your donation",
                      f"{current_user.name} requested your donation: {donor_med.name}. Visit dashboard to accept.")
    flash("Match request sent. Donor will be notified.", "info")
    return redirect(url_for("matches.find_matches"))

@matches_bp.route("/donor_accept/<int:match_id>", methods=["POST"])
@login_required
def donor_accept(match_id):
    match = Match.query.get_or_404(match_id)
    # only donor can accept
    if match.donor_id != current_user.id:
        flash("Unauthorized", "danger"); return redirect(url_for("home"))
    match.status = "donor_accepted"
    db.session.commit()
    # notify requester
    requester = User.query.get(match.requester_id)
    send_notification(requester.email, "Your request accepted", f"Donor accepted the request for {match.donor_medicine.name}. Please confirm to reveal contact details.")
    flash("You accepted the request. Awaiting requester confirmation.", "success")
    return redirect(url_for("meds.my_donations"))

@matches_bp.route("/requester_confirm/<int:match_id>", methods=["POST"])
@login_required
def requester_confirm(match_id):
    match = Match.query.get_or_404(match_id)
    # only requester confirm
    if match.requester_id != current_user.id:
        flash("Unauthorized", "danger"); return redirect(url_for("home"))
    if match.status != "donor_accepted":
        flash("Match not ready", "warning"); return redirect(url_for("meds.my_requests"))
    # move to awaiting verification by doctors
    match.status = 'awaiting_verification'
    db.session.commit()
    # notify doctors to review this match
    doctors = User.query.filter_by(role='doctor').all()
    for d in doctors:
        try:
            send_notification(d.email, 'Match awaiting verification', f"A match (id={match.id}) requires verification. Review: {url_for('matches.verify', match_id=match.id, _external=True)}")
        except Exception:
            pass
    flash('Request submitted for doctor verification. A doctor will review and approve shortly.', 'info')
    return redirect(url_for('meds.my_requests'))


@matches_bp.route('/verify/<int:match_id>', methods=['GET','POST'])
@login_required
def verify(match_id):
    if current_user.role != 'doctor':
        flash('Unauthorized', 'danger'); return redirect(url_for('home'))
    match = Match.query.get_or_404(match_id)
    if request.method == 'POST':
        # approve images for both medicines
        from .models import Image
        imgs = Image.query.filter(Image.medicine_id.in_([match.donor_medicine_id, match.requester_medicine_id])).all()
        for img in imgs:
            img.approved = True
            img.approved_by = current_user.id
            img.approved_at = datetime.utcnow()
            db.session.add(img)
        # finalize match and reveal contacts
        match.status = 'completed'
        dm = match.donor_medicine; rm = match.requester_medicine
        dm.status = 'matched'; rm.status = 'matched'
        db.session.commit()
        donor = User.query.get(match.donor_id)
        requester = User.query.get(match.requester_id)
        body = f"Match completed after doctor verification. Donor: {donor.name}, Email: {donor.email}, Phone: {donor.phone}\nRequester: {requester.name}, Email: {requester.email}, Phone: {requester.phone}"
        send_notification(donor.email, 'Match verified & contact revealed', body)
        send_notification(requester.email, 'Match verified & contact revealed', body)
        flash('Match verified and contacts revealed. Emails sent.', 'success')
        return redirect(url_for('matches.pending_verifications'))
    # determine whether the current doctor can approve this match
    # only allow approving when match is awaiting_verification
    can_approve = (match.status == 'awaiting_verification')
    return render_template('matches/verify.html', match=match, can_approve=can_approve)