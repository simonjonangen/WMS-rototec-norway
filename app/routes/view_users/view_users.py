from flask import (
    Blueprint,
    render_template, request, flash, redirect, url_for
)
from app.routes.login.login import login_required
from app.routes.shared.utils import role_required
from app.google_sheets.sheets_service import get_sheet_values, write_cell
from app.config.roles import ALLOWED_ROLES

master_role = ALLOWED_ROLES[1]

view_users_bp = Blueprint(
    'view_users',
    __name__,
    template_folder='.'
)


@view_users_bp.route("/view_users", methods=["GET"], endpoint="view_users")
@login_required
@role_required(master_role)
def view_users():
    try:
        values = get_sheet_values("users", "A1:Z1000")
        if not values or len(values) < 2:
            return render_template("view_users.html", users=[])

        headers = values[0]
        users = [dict(zip(headers, row)) for row in values[1:] if row]
        return render_template("view_users.html", users=users)

    except Exception as e:
        print("❌ Error in /view_users:", e)
        return str(e), 500

def index_to_column_letter(index):
    """Convert a 0-based column index to a column letter (e.g., 0 -> A, 27 -> AB)."""
    result = ""
    while index >= 0:
        result = chr(index % 26 + ord('A')) + result
        index = index // 26 - 1
    return result

@view_users_bp.route("/update_user", methods=["POST"], endpoint="update_user")
@login_required
@role_required(master_role)
def update_user():
    try:
        user_id = request.form.get("user_id")
        name = request.form.get("name")
        email = request.form.get("email")
        role = request.form.get("role")
        pin = request.form.get("pin")

        if not user_id or not name or not email or not role:
            flash("All cells must be filled.", "danger")
            return redirect(url_for("view_users.view_users"))

        # Read the sheet
        values = get_sheet_values("users", "A1:Z1000")
        if not values:
            flash("❌ Error when reading users file.", "danger")
            return redirect(url_for("view_users.view_users"))

        headers = values[0]
        id_col = headers.index("id")
        row_to_update = None

        for idx, row in enumerate(values[1:], start=2):  # row 2 = first user row
            row += [""] * (len(headers) - len(row))  # pad short rows
            if row[id_col] == user_id:
                row_to_update = idx
                break

        if not row_to_update:
            flash("❌ User not found.", "danger")
            return redirect(url_for("view_users.view_users"))

        # Update specified fields
        updates = {
            "name": name,
            "email": email,
            "role": role,
        }
        if pin:
            updates["pin"] = pin

        for key, val in updates.items():
            if key in headers:
                col_idx = headers.index(key)
                col_letter = index_to_column_letter(col_idx)
                cell = f"{col_letter}{row_to_update}"
                write_cell("users", cell, val)

        flash("✅ User information updated.", "success")

    except Exception as e:
        print("❌ Error in /update_user:", e)
        flash("❌ Error when updating user information.", "danger")

    return redirect(url_for("view_users.view_users"))
