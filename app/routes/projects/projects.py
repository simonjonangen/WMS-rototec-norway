from flask import Blueprint, render_template, session, redirect, url_for
from app.google_sheets.sheets_service import get_sheet_values
from datetime import datetime
import json
from app.config.roles import ALLOWED_ROLES

projects_bp = Blueprint("projects", __name__, template_folder=".")

master_role = ALLOWED_ROLES[1]  # Assuming index 1 corresponds to master/project manager

def _safe_json_list(val):
    s = (val or "").strip()
    if not s:  # empty cell
        return []
    try:
        v = json.loads(s)
        # Coerce non-list into a list
        if isinstance(v, dict):
            return [v]
        if isinstance(v, list):
            # keep only dict-like entries; ignore stray strings/numbers
            return [x for x in v if isinstance(x, dict)]
        return []
    except Exception:
        return []

def _to_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


@projects_bp.route("/projects")
def projects():
    user_email = session.get("username")
    user_role = session.get("role")

    raw = get_sheet_values("projects", "A1:Z1000")
    if not raw or len(raw) < 2:
        return render_template("projects.html", projects=[])

    headers = raw[0]
    data = raw[1:]

    projects = []
    for row in data:
        project = dict(zip(headers, row))
        try:
            created_by = (project.get("created_by", "") or "").strip()

            # SAFE parse once
            workers_list = _safe_json_list(project.get("workers"))
            items_list   = _safe_json_list(project.get("items"))
            taken_list   = _safe_json_list(project.get("taken_by_worker"))
            returned_list = _safe_json_list(project.get("returned_by_worker"))

            # visibility (creator OR assigned; masters see all)
            def _norm(x):
                return (x or "").strip().lower()

            # Build the current user's identifiers and DROP empties
            me_ids = {_norm(session.get("username")), _norm(session.get("email")), _norm(session.get("name"))}
            me_ids.discard("")  # <-- critical: no empty string

            # For each worker, build a set of ids and DROP empties, then intersect
            assigned_match = any(
                (
                    lambda worker_ids: (
                        worker_ids.discard(""),  # mutate to remove ""
                        bool(worker_ids & me_ids)
                    )[1]
                )({
                    _norm(w.get("username")),
                    _norm(w.get("email")),
                    _norm(w.get("name")),
                })
                for w in workers_list
            )

            # Created-by match (only if we have a real identifier)
            creator_id = _norm(created_by)
            creator_match = (creator_id != "" and creator_id in me_ids)

            if not (creator_match or assigned_match):
                continue

            # dynamic status
            start_date = project.get("start_date", "")
            end_date   = project.get("end_date", "")
            original_status = (project.get("status") or "active").lower()
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt   = datetime.strptime(end_date, "%Y-%m-%d")
                today    = datetime.today()
                if original_status == "active":
                    if today < start_dt:
                        dynamic_status = "upcoming"
                    elif start_dt <= today <= end_dt:
                        dynamic_status = "active"
                    else:
                        dynamic_status = "active"
                else:
                    dynamic_status = original_status
            except Exception as e:
                print(f"❌ Date parsing error: {e}")
                dynamic_status = original_status

            # ⬇️ NEW: do not show finished projects on this page
            if dynamic_status == "finished":
                continue

            # sum taken quantities (fallback to +1 if missing)
            taken_quantities = {}
            for t in taken_list:
                item_id = t.get("item_id")
                if not item_id:
                    continue
                q = _to_int(t.get("quantity"), default=1)
                taken_quantities[item_id] = taken_quantities.get(item_id, 0) + q

            # sum returned quantities (fallback to +1 if missing)
            returned_quantities = {}
            for r in returned_list:
                item_id = r.get("item_id")
                if not item_id:
                    continue
                q = _to_int(r.get("quantity"), default=1)
                returned_quantities[item_id] = returned_quantities.get(item_id, 0) + q

            # build items for the card
            project_items = []
            for i in items_list:
                item_id = i.get("item_id", "")
                projected_quantity = _to_int(i.get("quantity"), default=0)
                used_quantity = taken_quantities.get(item_id, 0)
                returned_quantity = returned_quantities.get(item_id, 0)
                project_items.append({
                    "item_id": item_id,
                    "item_name": i.get("item_name", ""),
                    "projected_quantity": projected_quantity,
                    "used_quantity": used_quantity,  # taken
                    "returned_quantity": returned_quantity,  # returned
                    "is_taken": used_quantity > 0
                })

            projects.append({
                "project_number": project.get("project_number", "N/A"),
                "created_by": created_by,
                "start_date": start_date,
                "end_date": end_date,
                "status": dynamic_status,
                "workers": [w.get("name") or w.get("username") for w in workers_list],
                "project_items": project_items,
                "items_count": len(items_list),
                "customer_name": project.get("customer_name") or project.get("project_address") or ""
            })

        except Exception as e:
            print(f"❌ Error parsing project row: {e}")
            continue

    def parse_date(d):
        try:
            return datetime.strptime(d, "%Y-%m-%d")
        except:
            return datetime.max

    projects.sort(key=lambda p: parse_date(p["start_date"]))
    return render_template("projects.html", projects=projects, is_master=(user_role == master_role))


from flask import request, jsonify
from app.google_sheets.sheets_service import get_sheet_values, update_row

@projects_bp.route("/api/update_project_item", methods=["POST"])
def update_project_item():
    if session.get("role") != ALLOWED_ROLES[1]:  # Only manager
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    project_number = data.get("project_number")
    item_id = data.get("item_id")
    new_quantity = data.get("quantity")
    delete = data.get("delete", False)

    if not project_number or not item_id:
        return jsonify({"error": "Missing data"}), 400

    # Get full project sheet
    raw = get_sheet_values("projects", "A1:Z1000")
    if not raw or len(raw) < 2:
        return jsonify({"error": "No project data"}), 404

    headers = raw[0]
    for i, row in enumerate(raw[1:], start=2):  # start=2 because of header and 1-based sheet rows
        project = dict(zip(headers, row))
        if project.get("project_number") == project_number:
            try:
                items = json.loads(project.get("items", "[]"))
                items = [i for i in items if isinstance(i, dict)]
                updated = False

                for idx, itm in enumerate(items):
                    if itm.get("item_id") == item_id:
                        if delete:
                            items.pop(idx)
                        else:
                            itm["quantity"] = int(new_quantity)
                        updated = True
                        break

                    if not updated and data.get("add"):
                        items.append({
                            "item_id": item_id,
                            "item_name": data.get("item_name", ""),
                            "quantity": int(new_quantity)
                        })
                        updated = True

                if not updated:
                    return jsonify({"error": "Item not found in project"}), 404

                row_index = i  # actual sheet row
                updated_row = list(row)
                item_col_index = headers.index("items")
                updated_row[item_col_index] = json.dumps(items)
                update_row("projects", row_index, updated_row)
                return jsonify({"success": True}), 200

            except Exception as e:
                return jsonify({"error": str(e)}), 500

    return jsonify({"error": "Project not found"}), 404


@projects_bp.route('/finished_projects', endpoint='finished_projects')
def finished_projects_shortcut():
    # Always send users to the route that actually loads finished projects
    return redirect(url_for('projects.projects_finished'))


@projects_bp.route("/projects/finished")
def projects_finished():
    user_email = session.get("username")
    user_role = session.get("role")

    raw = get_sheet_values("projects", "A1:Z1000")
    if not raw or len(raw) < 2:
        return render_template("finished_projects.html", projects=[], is_master=(user_role == master_role))

    headers = raw[0]
    data = raw[1:]

    projects = []
    for row in data:
        project = dict(zip(headers, row))
        try:
            created_by = (project.get("created_by", "") or "").strip()

            # parse once
            workers_list  = _safe_json_list(project.get("workers"))
            items_list    = _safe_json_list(project.get("items"))
            taken_list    = _safe_json_list(project.get("taken_by_worker"))
            returned_list = _safe_json_list(project.get("returned_by_worker"))

            # visibility (creator OR assigned; masters see all)
            def _norm(x):
                return (x or "").strip().lower()

            # Build the current user's identifiers and DROP empties
            me_ids = {_norm(session.get("username")), _norm(session.get("email")), _norm(session.get("name"))}
            me_ids.discard("")  # <-- critical: no empty string

            # For each worker, build a set of ids and DROP empties, then intersect
            assigned_match = any(
                (
                    lambda worker_ids: (
                        worker_ids.discard(""),  # mutate to remove ""
                        bool(worker_ids & me_ids)
                    )[1]
                )({
                    _norm(w.get("username")),
                    _norm(w.get("email")),
                    _norm(w.get("name")),
                })
                for w in workers_list
            )

            # Created-by match (only if we have a real identifier)
            creator_id = _norm(created_by)
            creator_match = (creator_id != "" and creator_id in me_ids)

            if not (creator_match or assigned_match):
                continue

            # status: we only want 'finished'
            original_status = (project.get("status") or "").strip().lower()
            if original_status != "finished":
                continue

            # sum taken quantities
            taken_quantities = {}
            for t in taken_list:
                item_id = t.get("item_id")
                if not item_id:
                    continue
                q = _to_int(t.get("quantity"), default=1)
                taken_quantities[item_id] = taken_quantities.get(item_id, 0) + q

            # sum returned quantities
            returned_quantities = {}
            for r in returned_list:
                item_id = r.get("item_id")
                if not item_id:
                    continue
                q = _to_int(r.get("quantity"), default=1)
                returned_quantities[item_id] = returned_quantities.get(item_id, 0) + q

            # build items
            project_items = []
            for i in items_list:
                item_id = i.get("item_id", "")
                projected_quantity = _to_int(i.get("quantity"), default=0)
                used_quantity = taken_quantities.get(item_id, 0)
                returned_quantity = returned_quantities.get(item_id, 0)
                project_items.append({
                    "item_id": item_id,
                    "item_name": i.get("item_name", ""),
                    "projected_quantity": projected_quantity,
                    "used_quantity": used_quantity,
                    "returned_quantity": returned_quantity,
                    "is_taken": used_quantity > 0
                })

            projects.append({
                "project_number": project.get("project_number", "N/A"),
                "created_by": created_by,
                "start_date": project.get("start_date", ""),
                "end_date": project.get("end_date", ""),
                "status": "finished",
                "workers": [w.get("name") or w.get("username") for w in workers_list],
                "project_items": project_items,
                "items_count": len(items_list),
                "customer_name": project.get("customer_name") or project.get("project_address") or ""
            })

        except Exception as e:
            print(f"❌ Error parsing project row (finished view): {e}")
            continue

    # (Optional) sort by end_date descending so most recently finished appear first
    def parse_date(d):
        from datetime import datetime
        try:
            return datetime.strptime(d, "%Y-%m-%d")
        except:
            return datetime.min

    projects.sort(key=lambda p: parse_date(p["end_date"]), reverse=True)

    return render_template("finished_projects.html", projects=projects, is_master=(user_role == master_role))


@projects_bp.route(
    "/api/projects/<project_number>/status",
    methods=["POST"],
    endpoint="projects_update_status"   # ensure endpoint name is unique in your app
)
def projects_update_status(project_number):
    # Manager-only (same rule you use elsewhere)
    if session.get("role") != ALLOWED_ROLES[1]:
        return jsonify({"ok": False, "error": "Unauthorized"}), 403

    payload = request.get_json(silent=True) or {}
    new_status = (payload.get("status") or "").strip().lower()

    # <-- allow flipping between finished <-> active
    if new_status not in ("finished", "active"):
        return jsonify({"ok": False, "error": "Status must be 'finished' or 'active'."}), 400

    raw = get_sheet_values("projects", "A1:Z1000")
    if not raw or len(raw) < 2:
        return jsonify({"ok": False, "error": "No project data"}), 404

    headers = raw[0]
    try:
        status_idx = headers.index("status")
        pn_idx = headers.index("project_number")
    except ValueError:
        return jsonify({"ok": False, "error": "Sheet missing required columns"}), 500

    # find the matching row and write new status
    for i, row in enumerate(raw[1:], start=2):  # sheet row numbers (header is row 1)
        if (len(row) > pn_idx) and str(row[pn_idx]) == str(project_number):
            updated_row = list(row)
            if len(updated_row) < len(headers):
                updated_row += [""] * (len(headers) - len(updated_row))
            updated_row[status_idx] = new_status
            try:
                update_row("projects", i, updated_row)
            except Exception as e:
                return jsonify({"ok": False, "error": str(e)}), 500

            return jsonify({"ok": True, "project_number": project_number, "status": new_status}), 200

    return jsonify({"ok": False, "error": "Project not found"}), 404
