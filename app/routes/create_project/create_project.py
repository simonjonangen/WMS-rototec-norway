from flask import (
    Blueprint, render_template, request, session, jsonify, send_from_directory
)
from datetime import datetime
from app.routes.login.login import login_required
from app.routes.shared.utils import role_required
from app.config.roles import ALLOWED_ROLES
from app.google_sheets.sheets_service import get_sheet_values, append_row
import json
import os
import uuid

create_project_bp = Blueprint(
    'create_project',
    __name__,
    template_folder='.'
)

master_role = ALLOWED_ROLES[1]

@create_project_bp.route('/create_project')
@login_required
def create_project():
    role = session.get('role')
    return render_template('create_project.html', role=role)

@create_project_bp.route('/create_project_js/<path:filename>')
def create_project_js(filename):
    return send_from_directory(os.path.dirname(__file__), filename)

@create_project_bp.route("/api/projects", methods=["GET"])
def get_projects():
    try:
        search = request.args.get("search", "").lower()

        raw = get_sheet_values("projects", "A1:Z1000")
        if not raw:
            return jsonify([])

        headers = raw[0]
        projects = [dict(zip(headers, row)) for row in raw[1:] if len(row) >= len(headers)]

        if search:
            projects = [
                p for p in projects
                if search in (p.get("project_number") or "").lower()
            ]

        return jsonify(projects)

    except Exception as e:
        print("❌ Error in /api/projects:", e)
        return jsonify({"error": str(e)}), 500


@create_project_bp.route("/api/create_project", methods=["POST"])
@login_required
@role_required(master_role)
def create_project_api():
    try:
        data = request.get_json()
        project_number = data.get("project_number")
        customer_name = data.get("customer_name", "")
        workers = data.get("workers", [])
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        items = data.get("items", [])
        created_by = session.get("username") or "unknown@user.no"

        if not project_number:
            return jsonify({"success": False, "error": "Project number is required"}), 400

        # Create project entry
        project_id = str(uuid.uuid4())
        append_row("projects", [
            project_id,
            project_number,
            start_date,
            end_date,
            created_by,
            datetime.utcnow().isoformat(),
            "active",
            json.dumps(workers),
            json.dumps(items),
            customer_name
        ])

        print("✅ Project created successfully")
        return jsonify({
            "success": True,
            "message": "Project created successfully",
            "project_id": project_id,
            "status": "success"  # Explicit status for frontend
        }), 200

    except Exception as e:
        print("❌ Error in /api/create_project:", e)
        return jsonify({
            "success": False,
            "error": str(e),
            "message": "Failed to create project",
            "status": "error"
        }), 500

@create_project_bp.route("/api/get_workers", methods=["GET"])
@login_required
def get_workers():
    try:
        raw = get_sheet_values("users", "A1:Z1000")
        if not raw:
            return jsonify([])

        headers = raw[0]
        users = [dict(zip(headers, row)) for row in raw[1:] if len(row) >= len(headers)]

        workers = [
            {"username": u.get("email"), "name": u.get("name")}
            for u in users
            if u.get("role") == "worker"
        ]

        return jsonify(workers)

    except Exception as e:
        print("❌ Error in /api/get_workers:", e)
        return jsonify({"error": str(e)}), 500