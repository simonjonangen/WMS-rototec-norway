from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
import traceback
from app.routes.login.login import login_required
from app.routes.shared.utils import insert_log_entry
from app.google_sheets.sheets_service import (
    get_all_items,
    get_item_by_id,
    insert_log,
    get_sheet_values
)

catalog_bp = Blueprint(
    'catalog',
    __name__,
    template_folder='.'
)

@catalog_bp.route('/inventory')
def inventory_redirect():
    try:
        return redirect(url_for('catalog.catalog_view'))
    except Exception as e:
        print("❌ Error in /inventory redirect:", e)
        traceback.print_exc()
        return str(e), 500

@catalog_bp.route('/catalog')
@login_required
def catalog_view():
    try:
        query = request.args.get('q', '').strip().lower()
        category_filter = request.args.get('category', '')
        supplier_filter = request.args.get('supplier', '')
        location_filter = request.args.get('location', '')
        page = int(request.args.get('page', 1))
        per_page = 24

        items = get_all_items()

        def match(item):
            q_fields = [
                str(item.get('product_name', '')).lower(),
                str(item.get('article_number', '')).lower(),
                str(item.get('category', '')).lower(),
                str(item.get('supplier', '')).lower(),
                str(item.get('location', '')).lower()
            ]
            matches_query = not query or any(query in field for field in q_fields)
            matches_category = not category_filter or item.get('category') == category_filter
            matches_supplier = not supplier_filter or item.get('supplier') == supplier_filter
            matches_location = not location_filter or item.get('location') == location_filter
            return matches_query and matches_category and matches_supplier and matches_location

        filtered_items = list(filter(match, items))

        total_items = len(filtered_items)
        total_pages = max((total_items + per_page - 1) // per_page, 1)
        start = (page - 1) * per_page
        paginated_items = filtered_items[start:start + per_page]

        unique_categories = sorted(set(item.get('category') or 'Undecided' for item in items))
        unique_suppliers = sorted(set(item.get('supplier') or 'Unknown' for item in items))
        unique_locations = sorted(set(item.get('location') or 'Undecided' for item in items))

        zero_stock_items = [item for item in items if str(item.get("stock", "0")).strip() == "0"]
        unreturned = []

        if zero_stock_items:
            article_numbers = [item["article_number"] for item in zero_stock_items]
            logs_raw = get_sheet_values("logs", "A1:Z1000")
            if not logs_raw:
                logs = []
            else:
                headers = logs_raw[0]
                logs = [
                    dict(zip(headers, row)) for row in logs_raw[1:]
                    if row and dict(zip(headers, row)).get("article_number") in article_numbers
                ]

            log_summary = {}
            for log in logs:
                key = (log["article_number"], log["user_name"])
                qty = int(log.get("quantity", 0))
                if log["action"] == "take":
                    log_summary[key] = log_summary.get(key, 0) + qty
                elif log["action"] == "return":
                    log_summary[key] = log_summary.get(key, 0) - qty

            for (article, user), net_qty in log_summary.items():
                if net_qty > 0:
                    unreturned.append({
                        "article_number": article,
                        "user": user,
                        "quantity": net_qty
                    })

        return render_template(
            'catalog.html',
            role=session.get('role'),
            items=paginated_items,
            unique_categories=unique_categories,
            unique_suppliers=unique_suppliers,
            unique_locations=unique_locations,
            page=page,
            total_pages=total_pages,
            unreturned=unreturned
        )

    except Exception as e:
        print("❌ Error in /catalog:", e)
        traceback.print_exc()
        return str(e), 400



@catalog_bp.route('/api/search_items', methods=['GET'])
def search_items():
    query = request.args.get("query", "").lower()
    items = get_all_items()
    matched = [i for i in items if query in (i.get("product_name") or "").lower()]
    return jsonify(matched)

@catalog_bp.route("/api/search_item")
def search_item():
    query = request.args.get("q", "").strip().lower()

    # Early exit for empty or too-short queries
    if not query or len(query) < 2:
        return jsonify([])

    values = get_sheet_values("products", "A1:Z1000")
    if not values:
        return jsonify([])

    headers = values[0]
    matched = []

    for row in values[1:]:
        item = dict(zip(headers, row))
        name = (item.get("product_name") or "").lower()
        number = (item.get("article_number") or "").lower()
        if query in name or query in number:
            matched.append(item)
            if len(matched) >= 20:  # Cap results to prevent large responses
                break

    return jsonify(matched)




@catalog_bp.route("/zero_stock_log_check", methods=["GET"])
@login_required
def check_zero_stock_items_logs():
    try:
        # Step 1: Get all items and filter for stock = 0
        all_items = get_all_items()
        zero_stock_items = [
            item for item in all_items
            if str(item.get("stock", "0")).strip() == "0"
        ]

        if not zero_stock_items:
            return jsonify({"message": "No items with zero stock"}), 200

        article_numbers = [item["article_number"] for item in zero_stock_items]

        # Step 2: Fetch all logs
        logs_raw = get_sheet_values("logs", "A1:Z1000")
        if not logs_raw:
            return jsonify({"message": "No logs found"}), 200

        headers = logs_raw[0]
        logs = [
            dict(zip(headers, row)) for row in logs_raw[1:]
            if row and dict(zip(headers, row)).get("article_number") in article_numbers
        ]

        # Step 3: Summarize log quantities
        unmatched = []
        log_summary = {}

        for log in logs:
            key = (log["article_number"], log["user_name"])
            qty = int(log.get("quantity", 0))
            if log["action"] == "take":
                log_summary[key] = log_summary.get(key, 0) + qty
            elif log["action"] == "return":
                log_summary[key] = log_summary.get(key, 0) - qty

        # Step 4: Identify unreturned items
        for (article, user), net_qty in log_summary.items():
            if net_qty > 0:
                unmatched.append({
                    "article_number": article,
                    "user": user,
                    "not_returned_qty": net_qty,
                    "product_name": next(
                        (i["product_name"] for i in zero_stock_items if i["article_number"] == article),
                        "Unknown"
                    )
                })

        return jsonify(unmatched), 200

    except Exception as e:
        print("❌ Error in /zero_stock_log_check:", e)
        traceback.print_exc()
        return jsonify({"error": "Server error"}), 500
