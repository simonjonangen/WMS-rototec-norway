from flask import Blueprint, render_template, session
from app.google_sheets.sheets_service import get_sheet_values
from datetime import datetime
import json
from app.config.roles import ALLOWED_ROLES

project_logs_bp = Blueprint("project_logs", __name__, template_folder=".")

@project_logs_bp.route("/project_logs")
def project_logs():
    user_email = session.get("username")
    user_role = session.get("role")
    is_master = user_role == ALLOWED_ROLES[1]

    raw = get_sheet_values("projects", "A1:Z1000")
    if not raw or len(raw) < 2:
        return render_template("project_logs.html", active=[], upcoming=[], completed=[])

    headers = raw[0]
    data = raw[1:]

    active = []
    upcoming = []
    completed = []

    for row in data:
        project = dict(zip(headers, row))
        try:
            workers = json.loads(project.get("workers", "[]"))
            items = json.loads(project.get("items", "[]"))

            if not is_master:
                if not any(user_email == w.get("username") for w in workers):
                    continue

            start_date = project.get("start_date", "")
            end_date = project.get("end_date", "")
            status = project.get("status", "active").lower()

            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                today = datetime.today()

                if status == "completed":
                    target_list = completed
                elif today < start_dt:
                    target_list = upcoming
                elif start_dt <= today <= end_dt:
                    target_list = active
                else:
                    target_list = completed if status == "completed" else active
            except:
                target_list = active

            target_list.append({
                "project_number": project.get("project_number", "N/A"),
                "created_by": project.get("created_by", "Unknown"),
                "start_date": start_date,
                "end_date": end_date,
                "workers": [w.get("name") or w.get("username") for w in workers],
                "project_items": [{
                    "item_id": i.get("item_id", ""),
                    "item_name": i.get("item_name", ""),
                    "quantity": i.get("quantity", "")
                } for i in items],
                "status": status,
                "items_count": len(items),
                "logs": []  # placeholder for take/return events if you want to add later
            })

        except Exception as e:
            print(f"❌ Error processing project row: {e}")
            continue

    return render_template("project_logs.html", active=active, upcoming=upcoming, completed=completed)
