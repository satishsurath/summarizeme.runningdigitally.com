"""Admin blueprint — admin settings, role update, add user."""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app_config import SessionLocal, require_role
from db.models import User

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin-settings")
@require_role(["admin"])
def admin_settings():
    """A page to manage user roles."""
    session = SessionLocal()
    try:
        users = session.query(User).all()
        return render_template("admin_settings.html", users=users)
    finally:
        session.close()


@admin_bp.route("/admin-update-role", methods=["POST"])
@require_role(["admin"])
def admin_update_role():
    new_role = request.form.get("role")
    user_id = request.form.get("user_id")

    if not new_role or not user_id:
        abort(400, "Missing parameters")

    session = SessionLocal()
    try:
        user_obj = session.query(User).get(user_id)
        if not user_obj:
            abort(404, "User not found")
        user_obj.role = new_role
        session.commit()
    finally:
        session.close()

    return redirect(url_for("admin_settings"))


@admin_bp.route("/admin-add-user", methods=["POST"])
@require_role(["admin"])
def admin_add_user():
    """Endpoint to create a new user with a given email and role."""
    new_email = request.form.get("new_email", "").strip()
    new_role = request.form.get("new_role", "reader").strip()

    if not new_email:
        flash("No email provided.", "error")
        return redirect(url_for("admin_settings"))

    if "@" not in new_email:
        flash("Invalid email format.", "error")
        return redirect(url_for("admin_settings"))

    session = SessionLocal()
    try:
        existing_user = session.query(User).filter_by(email=new_email).first()
        if existing_user:
            existing_user.role = new_role
            session.commit()
            flash(f"Updated existing user '{new_email}' to role '{new_role}'.", "info")
        else:
            new_user = User(email=new_email, role=new_role)
            session.add(new_user)
            session.commit()
            flash(f"Created new user '{new_email}' with role '{new_role}'.", "success")
    finally:
        session.close()

    return redirect(url_for("admin_settings"))
