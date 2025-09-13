# file: item_detail.py
from flask import Blueprint, render_template, request, jsonify, session, send_from_directory
import traceback
from app.routes.login.login import login_required
from app.routes.shared.utils import insert_log_entry
from app.google_sheets.sheets_service import get_item_by_id
import os

item_bp = Blueprint("item_detail", __name__, template_folder=".")

# Route to serve the JS manually
@item_bp.route("/take_item/take_item.js")
def serve_take_item_js():
    try:
        js_dir = os.path.join(os.path.dirname(__file__), "../take_item")
        return send_from_directory(js_dir, "take_item.js")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to serve the JS manually
@item_bp.route("/return_item/return_item.js")
def serve_return_item_js():
    try:
        js_dir = os.path.join(os.path.dirname(__file__), "../return_item")
        return send_from_directory(js_dir, "return_item.js")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@item_bp.route("/item/<string:item_id>", methods=["GET"])
@login_required
def item_detail(item_id):
    try:
        item, logs = get_item_by_id(item_id)
        for log in logs:
            log["user_name"] = log.get("user_name", "Unknown")

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return render_template("item_detail.html", item=item, logs=logs)

        return render_template("item_detail.html", item=item, logs=logs, role=session.get("role"))
    except Exception as e:
        print("❌ Error in /item/<id>:", e)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 400
