from flask import Blueprint, render_template, session, send_from_directory, request, jsonify
from app.routes.login.login import login_required
from app.google_sheets.sheets_service import get_sheet_values, insert_log
import os, json

take_item_bp = Blueprint(
    'take_item',
    __name__,
    template_folder='.'
)

@take_item_bp.route('/take_item', endpoint='take_item')
@login_required
def take_item():
    role = session.get('role')
    return render_template('take_item.html', role=role)

@take_item_bp.route('/take_item_js/<path:filename>')
def take_item_js(filename):
    return send_from_directory(os.path.dirname(__file__), filename)

@take_item_bp.route("/api/project_items", methods=["POST"])
def get_project_items():
    from flask import session, request, jsonify
    current_user = session.get("username", "").strip().lower()
    data = request.get_json()
    project_number = data.get("project_number", "").strip()

    raw = get_sheet_values("projects", "A1:Z1000")
    if not raw or len(raw) < 2:
        return jsonify({"error": "No project data"}), 404

    headers = raw[0]
    for row in raw[1:]:
        project = dict(zip(headers, row))

        if project.get("project_number", "").strip() == project_number:
            workers_raw = project.get("workers", "[]")
            try:
                workers = json.loads(workers_raw)
            except Exception as e:
                return jsonify({"error": "Invalid worker data"}), 500

            worker_names = [w.get("name", "").strip().lower() for w in workers]
            if current_user not in worker_names:
                return jsonify({"error": "Not authorized for this project"}), 403

            # Parse items
            try:
                items = json.loads(project.get("items", "[]"))
            except Exception as e:
                return jsonify({"error": "Invalid item data"}), 500

            # Get catalog data
            catalog_raw = get_sheet_values("products", "A1:Z1000")
            if not catalog_raw or len(catalog_raw) < 2:
                return jsonify({"error": "Catalog unavailable"}), 500

            catalog_headers = catalog_raw[0]
            catalog_data = [dict(zip(catalog_headers, row)) for row in catalog_raw[1:]]

            # Match and enrich items
            enriched = []
            for item in items:
                match = next((c for c in catalog_data if c.get("article_number") == item.get("item_id")), {})
                enriched.append({
                    "item_id": item.get("item_id"),
                    "item_name": item.get("item_name"),
                    "quantity": item.get("quantity"),
                    "location": match.get("location", "-"),
                    "unit": match.get("unit", "-"),
                    "type": match.get("category", "-"),  # `type` maps to your `category`
                    "available": match.get("stock", "-"),  # `available` maps to your `stock`
                    "image_url": match.get("product_image_url", "")
                })

            return jsonify({"items": enriched}), 200

    return jsonify({"error": "Project not found"}), 404

from flask import Blueprint, request, jsonify, session
import json
from app.google_sheets.sheets_service import update_row


@take_item_bp.route("/api/insert_project_items", methods=["POST"])
def insert_project_items():
    current_user = session.get("username", "").strip()
    data = request.get_json()

    project_number = data.get("project_number", "").strip()
    items = data.get("items", [])

    if not current_user or not project_number or not isinstance(items, list):
        return jsonify({"error": "Missing required fields or invalid data"}), 400

    raw = get_sheet_values("projects", "A1:Z1000")
    if not raw or len(raw) < 2:
        return jsonify({"error": "Projects sheet unavailable"}), 500

    headers = raw[0]
    for idx, row in enumerate(raw[1:], start=2):
        project = dict(zip(headers, row))
        if project.get("project_number", "").strip() == project_number:
            try:
                existing = json.loads(project.get("taken_by_worker", "[]"))
            except Exception:
                existing = []

            for item in items:
                if not isinstance(item, dict):
                    continue
                existing.append({
                    "item_id": item.get("article_number"),
                    "item_name": item.get("product_name", ""),
                    "quantity": int(item.get("quantity", 0))
                })

            updated_row = list(row)
            col_index = headers.index("taken_by_worker")
            while len(updated_row) <= col_index:
                updated_row.append("")
            updated_row[col_index] = json.dumps(existing)
            update_row("projects", idx, updated_row)
            return jsonify({"success": True}), 200

    return jsonify({"error": "Project not found"}), 404
