from flask import (
    Blueprint,
    flash, render_template, request, redirect, url_for
)
from app.routes.login.login import login_required
from app.routes.shared.utils import role_required
from app.config.roles import ALLOWED_ROLES
from datetime import datetime
import uuid

from app.google_sheets.sheets_service import append_row

add_user_bp = Blueprint(
    'add_user',
    __name__,
    template_folder='.'
)

master_role = ALLOWED_ROLES[1]

@add_user_bp.route("/add_user", methods=["GET", "POST"], endpoint="add_user")
@login_required
@role_required(master_role)
def add_user():
    try:
        if request.method == "POST":
            name = request.form.get("name")
            email = request.form.get("username")
            pin = request.form.get("pin")
            role = request.form.get("role")

            if not name or not email or not pin or not role:
                return "Missing required fields", 400

            user_data = [
                str(uuid.uuid4()),  # id
                datetime.utcnow().isoformat(),  # created_at ✅ move this up
                name,  # name
                email,  # email
                pin,  # pin
                role  # role
            ]

            append_row('users', user_data)

            flash("✅ User added!", "success")
            return redirect(url_for("view_users.view_users"))

        return render_template("add_user.html")

    except Exception as e:
        print("❌ Error in /add_user:", e)
        flash("❌ Internal error when adding user.", "danger")
        return str(e), 500
