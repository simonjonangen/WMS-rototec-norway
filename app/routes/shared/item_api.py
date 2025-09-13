from flask import Blueprint, request, jsonify, session
import traceback
import json
from app.routes.login.login import login_required

from app.google_sheets.sheets_service import (
    get_all_items,
    update_item_stock,
    insert_log
)


item_api_bp = Blueprint('item_api', __name__, url_prefix='/api')


@item_api_bp.route('/get_item_by_qr', methods=['POST'])
def get_item_by_qr():
    try:
        data = request.get_json()
        qr = data.get("qr_code", "").strip().lower()
        print(f"🔍 Scanned QR: {qr}")

        items = get_all_items()
        for item in items:
            article = (item.get("article_number") or "").strip().lower()
            if qr == article:
                print(f"✅ Match found: {item['product_name']} ({article})")
                return jsonify(item)

        print("❌ No match for QR vs article_number")
        return jsonify({"error": "Not found"}), 404
    except Exception as e:
        print("🔥 Error during QR item lookup:", e)
        return jsonify({"error": "Server error"}), 500


@item_api_bp.route('/confirm', methods=['POST'])
@login_required
def confirm_items():
    try:
        summary = request.form.get("summary")
        user_name = session.get("username")
        if not summary:
            return "No data provided", 400

        items = json.loads(summary)
        all_items = get_all_items()
        article_to_id = {item["article_number"]: item["id"] for item in all_items}

        for itm in items:
            art = itm.get("article_number")
            qty = itm.get("quantity")
            act = itm.get("action", "take")

            if not art:
                return "Missing article_number", 400
            if qty is None:
                return "Missing quantity", 400

            # New: honor return_type / apply_to_stock for returns
            return_type = (itm.get("return_type") or "").strip().lower()
            apply_to_stock = bool(itm.get("apply_to_stock")) if "apply_to_stock" in itm else (return_type == "returned" and act == "return")

            prod_id = article_to_id.get(art)
            if not prod_id:
                return f"Unknown product {art}", 400

            try:
                # Only mutate stock when:
                #  - take: always decrease
                #  - return: ONLY if apply_to_stock is True (i.e., "returned")
                if act == "take":
                    update_item_stock(prod_id, qty, "take")
                elif act == "return":
                    if apply_to_stock:
                        update_item_stock(prod_id, qty, "return")
                    # else: skip stock change for "used"/"broken"
                else:
                    return "Invalid action; must be 'take' or 'return'", 400
            except ValueError as ve:
                return str(ve), 400

            # Log the event; store return_type in 'status' for reporting
            insert_log(art, qty, act, user_name, status=return_type)

        return "OK", 200

    except Exception:
        traceback.print_exc()
        return "Server error", 500



@item_api_bp.route("/products", methods=["GET"])
def get_all_products():
    try:
        items = get_all_items()
        return jsonify([
            {
                "article_number": i.get("article_number"),
                "product_description": i.get("product_description", "")
            } for i in items
        ])
    except Exception as e:
        print("❌ Error in /api/products:", e)
        return jsonify([]), 500

