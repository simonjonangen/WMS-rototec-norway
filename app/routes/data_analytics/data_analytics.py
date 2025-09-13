from app.config.roles import ALLOWED_ROLES
from flask import Blueprint, render_template, request, send_file, jsonify
from app.google_sheets.sheets_service import get_sheet_values, get_all_items, get_pending_delivery_articles
from app.routes.login.login import login_required
from app.routes.shared.utils import role_required
import pandas as pd
from datetime import datetime
from io import BytesIO
import pytz
from collections import Counter
from flask import Blueprint, render_template, request, send_file, jsonify
# add this import:
from app.google_sheets.sheets_service import set_comment_on_stock, update_row
import json
import ast
from app.google_sheets.sheets_service import append_row  # already exists in sheets_service.py



data_analytics_bp = Blueprint(
    'data_analytics',
    __name__,
    template_folder='.'
)

master_role = ALLOWED_ROLES[1]

def _to_int(val, default=0):
    try:
        if val is None:
            return default
        if isinstance(val, (int, float)):
            return int(val)
        s = str(val).strip()
        if s == "":
            return default
        return int(float(s))
    except Exception:
        return default

@data_analytics_bp.route("/data_analytics", endpoint="data_analytics")
@login_required
@role_required(master_role)
def view_analytics():
    """
    Renders the analytics page.

    On each page load:
      1) Runs the auto-export job to sync 'projects' -> 'data_analytics' (idempotent)
      2) Reads 'logs', 'issue_reports', and 'products' to compute:
         - top_users      (sum of TAKES by user)
         - top_items      (sum of TAKES by article, joined to product name)
         - daily_usage    (sum of TAKES per day)
         - issue_counts   (simple per-item count from issue_reports, if present)
         - low_stock      (items where stock < safety_stock)
      3) Reads 'data_analytics' to display the consolidated rows table (analytics_rows)
    """
    try:
        # 1) Auto-export (safe to run repeatedly thanks to idempotency)
        try:
            _export_projects_to_data_analytics_job()
        except Exception as e:
            print("⚠️ Auto-export failed:", e)

        # ---------------------------
        # Helpers
        # ---------------------------
        def _pick_col(df, options):
            for c in options:
                if c in df.columns:
                    return c
            return None

        # ---------------------------
        # 2) Build the rest of the page data
        # ---------------------------

        # --- LOGS ---
        logs_raw = get_sheet_values("logs", "A1:Z10000") or []
        logs_headers = logs_raw[0] if logs_raw else []
        logs_list = [dict(zip(logs_headers, row)) for row in logs_raw[1:]] if logs_headers else []
        logs_df = pd.DataFrame(logs_list)

        if not logs_df.empty:
            # Ensure expected columns exist
            for col in ["article_number", "quantity", "action", "user_name", "timestamp"]:
                if col not in logs_df.columns:
                    logs_df[col] = ""

            # quantity as int
            logs_df["quantity"] = logs_df["quantity"].apply(_to_int)

            # Build a date-only column for charting (prefer 'timestamp')
            def _to_date_str(s):
                try:
                    return pd.to_datetime(s).date().isoformat()
                except Exception:
                    return ""
            if "timestamp" in logs_df.columns and logs_df["timestamp"].notna().any():
                logs_df["day"] = logs_df["timestamp"].apply(_to_date_str)
            elif "created_at" in logs_df.columns:
                logs_df["day"] = logs_df["created_at"].apply(_to_date_str)
            else:
                logs_df["day"] = ""
        else:
            logs_df = pd.DataFrame(columns=["article_number", "quantity", "action", "user_name", "timestamp", "day"])

        # --- PRODUCTS (used for low_stock + name map for top_items) ---
        products_raw = get_sheet_values("products", "A1:Z10000") or []
        products_headers = products_raw[0] if products_raw else []
        products_list = [dict(zip(products_headers, row)) for row in products_raw[1:]] if products_headers else []
        products_df = pd.DataFrame(products_list)

        # Product name map: article_number -> product_name
        if not products_df.empty:
            article_col = _pick_col(products_df, ["article_number", "Article Number", "Article", "sku"])
            name_col    = _pick_col(products_df, ["product_name", "Item name", "Name", "product_description"])
            if article_col and name_col:
                name_map = dict(zip(products_df[article_col].astype(str), products_df[name_col].astype(str)))
            else:
                name_map = {}
        else:
            name_map = {}

        # --- TOP USERS (based on 'take') ---
        if not logs_df.empty:
            takes_df = logs_df[logs_df["action"].astype(str).str.lower() == "take"].copy()
            if not takes_df.empty and {"user_name", "quantity"}.issubset(takes_df.columns):
                top_users = (
                    takes_df.groupby("user_name", dropna=False)["quantity"]
                    .sum()
                    .reset_index()
                    .sort_values("quantity", ascending=False)
                    .head(10)
                )
            else:
                top_users = pd.DataFrame(columns=["user_name", "quantity"])
        else:
            top_users = pd.DataFrame(columns=["user_name", "quantity"])

        # --- MOST TAKEN ITEMS (sum of takes per article, attach name from products) ---
        if not logs_df.empty:
            takes_df = logs_df[logs_df["action"].astype(str).str.lower() == "take"].copy()
            if not takes_df.empty and {"article_number", "quantity"}.issubset(takes_df.columns):
                takes_grouped = (
                    takes_df.groupby("article_number", dropna=False)["quantity"]
                    .sum()
                    .reset_index()
                    .sort_values("quantity", ascending=False)
                    .head(10)
                )
                takes_grouped["product_name"] = takes_grouped["article_number"].astype(str).map(name_map).fillna("")
                top_items = takes_grouped[["product_name", "article_number", "quantity"]]
            else:
                top_items = pd.DataFrame(columns=["product_name", "article_number", "quantity"])
        else:
            top_items = pd.DataFrame(columns=["product_name", "article_number", "quantity"])

        # --- DAILY USAGE (taken-only) ---
        if not logs_df.empty:
            takes_df = logs_df[logs_df["action"].astype(str).str.lower() == "take"].copy()
            if not takes_df.empty and {"day", "quantity"}.issubset(takes_df.columns):
                daily_usage = (
                    takes_df.groupby("day", dropna=False)["quantity"]
                    .sum()
                    .reset_index()
                    .sort_values("day")
                )
            else:
                daily_usage = pd.DataFrame(columns=["day", "quantity"])
        else:
            daily_usage = pd.DataFrame(columns=["day", "quantity"])

        # --- ISSUES ---
        issues_raw = get_sheet_values("issue_reports", "A1:Z10000") or []
        issues_headers = issues_raw[0] if issues_raw else []
        issues_list = [dict(zip(issues_headers, row)) for row in issues_raw[1:]] if issues_headers else []
        issues_df = pd.DataFrame(issues_list)

        if not issues_df.empty:
            # Normalize a couple of common variants
            if "article_number" not in issues_df.columns and "Article Number" in issues_df.columns:
                issues_df = issues_df.rename(columns={"Article Number": "article_number"})
            if "product_name" not in issues_df.columns and "Item name" in issues_df.columns:
                issues_df = issues_df.rename(columns={"Item name": "product_name"})

            group_cols = [c for c in ["product_name", "article_number"] if c in issues_df.columns]
            if group_cols:
                issue_counts = (
                    issues_df.assign(issue_count=1)
                    .groupby(group_cols, dropna=False)["issue_count"]
                    .sum()
                    .reset_index()
                    .sort_values("issue_count", ascending=False)
                    .head(10)
                )
            else:
                issue_counts = pd.DataFrame(columns=["product_name", "article_number", "issue_count"])
        else:
            issue_counts = pd.DataFrame(columns=["product_name", "article_number", "issue_count"])

        # --- LOW STOCK ---
        low_stock = []
        for p in products_list:
            article = p.get("article_number") or p.get("Article Number") or p.get("Article") or ""
            name = p.get("product_name") or p.get("Item name") or p.get("Name") or p.get("product_description") or ""
            stock = _to_int(p.get("stock") or p.get("Stock") or p.get("current_stock"))
            safety = _to_int(p.get("safety_stock") or p.get("Safety stock") or p.get("safety"))
            delivery_on_way = str(p.get("delivery_on_the_way") or p.get("Delivery on the way") or "").strip().lower() in {
                "true", "1", "yes", "y"
            }

            if safety > 0 and stock < safety:
                low_stock.append({
                    "article_number": article,
                    "product_name": name,
                    "stock_int": stock,
                    "safety_stock_int": safety,
                    "deficit": max(safety - stock, 0),
                    "delivery_on_the_way": delivery_on_way
                })

        # 3) === Read 'data_analytics' to display consolidated rows ===
        da_values = get_sheet_values("data_analytics", "A1:L100000") or []
        analytics_rows = []
        if da_values and da_values[0]:
            hdr = da_values[0]
            for r in da_values[1:]:
                row = list(r) + [""] * (len(hdr) - len(r))  # pad short rows
                analytics_rows.append(dict(zip(hdr, row)))

        # 4) Render template
        return render_template(
            "data_analytics.html",
            top_users=top_users.to_dict(orient="records"),
            top_items=top_items.to_dict(orient="records"),
            daily_usage=daily_usage.to_dict(orient="records"),
            issue_counts=issue_counts.to_dict(orient="records"),
            low_stock=low_stock,
            analytics_rows=analytics_rows,
        )

    except Exception as e:
        print("❌ Error in view_analytics:", e)
        return str(e), 500


@data_analytics_bp.route("/data_analytics/stock_comment", methods=["POST"])
@login_required
@role_required(master_role)
def add_stock_comment():
    data = request.get_json(silent=True) or {}
    article_number = (data.get("article_number") or "").strip()
    comment = (data.get("comment") or "").strip()

    try:
        if not article_number:
            raise ValueError("article_number is required")
        # Write the comment into the products sheet
        set_comment_on_stock(article_number, comment)
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@data_analytics_bp.route("/data_analytics/stock_comment_clear", methods=["POST"])
@login_required
@role_required(master_role)
def clear_stock_comment():
    data = request.get_json(silent=True) or {}
    article_number = (data.get("article_number") or "").strip()

    try:
        if not article_number:
            raise ValueError("article_number is required")
        # Clearing the comment by setting it to an empty string
        set_comment_on_stock(article_number, "")
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


# data_analytics.py  (add near your other imports)
import json, ast
from flask import jsonify, render_template
from app.google_sheets.sheets_service import get_sheet_values, append_row

def _safe_parse_json(maybe_json_str, default):
    if not maybe_json_str:
        return default
    if isinstance(maybe_json_str, (list, dict)):
        return maybe_json_str
    s = str(maybe_json_str).strip()
    if not s:
        return default
    try:
        return json.loads(s)
    except Exception:
        try:
            return ast.literal_eval(s)
        except Exception:
            return default

def _export_projects_to_data_analytics_job():
    """
    UPSERT export from 'projects' to 'data_analytics'.

    - Key: (Article Number, Drilling unit / Project number, Order time)
    - If key exists: update the existing row with latest values
    - If key missing: append new row
    - If key exists and values are identical: skip

    Returns: (appended_count, updated_count, skipped_count)
    """
    # 1) Read existing analytics table and index by composite key
    da_values = get_sheet_values("data_analytics", "A1:L100000") or []
    if not da_values or not da_values[0]:
        da_headers = [
            "Article Number","Order time","Order status","Warehouse","Driller",
            "Drilling unit / Project number","Pickup time","Item name",
            "Projected quantity","Taken quantity","Returned quantity","Comments"
        ]
        existing = []
    else:
        da_headers = da_values[0]
        existing = da_values[1:]

    # header -> index
    hidx = {h: i for i, h in enumerate(da_headers)}

    def _get_idx(name, default=-1):
        return hidx.get(name, default)

    idx_article = _get_idx("Article Number", 0)
    idx_order   = _get_idx("Order time", 1)
    idx_proj    = _get_idx("Drilling unit / Project number", 5)

    # Build key -> (row_index_1based, row_values_padded)
    # Note: sheet data starts at row 2
    existing_map = {}
    for i, row in enumerate(existing, start=2):
        # pad to headers length for safe compare
        r = list(row) + [""] * (len(da_headers) - len(row))
        a = (r[idx_article] if idx_article >= 0 else "").strip()
        o = (r[idx_order]   if idx_order   >= 0 else "").strip()
        p = (r[idx_proj]    if idx_proj    >= 0 else "").strip()
        if a or o or p:
            existing_map[(a, p, o)] = (i, r)

    # 2) Read projects
    projects_raw = get_sheet_values("projects", "A1:Z10000")
    if not projects_raw or not projects_raw[0]:
        return 0, 0, 0  # nothing to do

    headers = projects_raw[0]
    rows = [dict(zip(headers, r)) for r in projects_raw[1:] if r]

    def to_int(x, default=0):
        try:
            if x is None: return default
            s = str(x).strip()
            return int(float(s)) if s else default
        except Exception:
            return default

    appended = 0
    updated  = 0
    skipped  = 0

    for proj in rows:
        # Parse JSON-like fields
        projected = _safe_parse_json(proj.get("items"), default=[])
        taken     = _safe_parse_json(proj.get("taken_by_worker"), default=[])
        returned  = _safe_parse_json(proj.get("returned_by_worker"), default=[])
        workers   = _safe_parse_json(proj.get("workers"), default=[])

        # Metadata
        order_time     = (proj.get("created_at") or "").strip()
        order_status   = (proj.get("status") or "").strip()
        warehouse      = (proj.get("customer_name") or "").strip()
        project_number = (proj.get("project_number") or "").strip()
        pickup_time    = (proj.get("start_date") or "").strip()

        # Driller
        driller = ""
        if isinstance(workers, list) and workers:
            w0 = workers[0] or {}
            driller = (w0.get("name") or w0.get("username") or "").strip()

        # Aggregate quantities per item_id
        names, proj_qty, taken_qty, returned_qty, return_types = {}, {}, {}, {}, {}

        def remember_name(it):
            iid = str(it.get("item_id", "")).strip()
            if not iid: return
            nm = (it.get("item_name") or "").strip()
            if nm and not names.get(iid):
                names[iid] = nm

        if isinstance(projected, list):
            for it in projected:
                iid = str(it.get("item_id", "")).strip()
                if not iid: continue
                remember_name(it)
                proj_qty[iid] = proj_qty.get(iid, 0) + to_int(it.get("quantity"), 0)

        if isinstance(taken, list):
            for it in taken:
                iid = str(it.get("item_id", "")).strip()
                if not iid: continue
                remember_name(it)
                taken_qty[iid] = taken_qty.get(iid, 0) + to_int(it.get("quantity"), 0)

        if isinstance(returned, list):
            for it in returned:
                iid = str(it.get("item_id", "")).strip()
                if not iid: continue
                remember_name(it)
                q = to_int(it.get("quantity"), 0)
                returned_qty[iid] = returned_qty.get(iid, 0) + q
                rtype = (it.get("return_type") or "").strip().lower()
                if rtype:
                    rtmap = return_types.setdefault(iid, {})
                    rtmap[rtype] = rtmap.get(rtype, 0) + q

        all_iids = sorted(set(proj_qty) | set(taken_qty) | set(returned_qty))

        for iid in all_iids:
            item_name    = names.get(iid, "")
            projected_q  = proj_qty.get(iid, 0)
            taken_q      = taken_qty.get(iid, 0)
            returned_q   = returned_qty.get(iid, 0)

            # Comment summarizing return categories
            comment = ""
            if iid in return_types:
                parts = [f"{k}:{v}" for k, v in return_types[iid].items()]
                if parts:
                    comment = "; ".join(parts)

            # Build row dict keyed by sheet headers (so we can order properly)
            row_dict = {
                "Article Number": iid,
                "Order time": order_time,
                "Order status": order_status,
                "Warehouse": warehouse,
                "Driller": driller,
                "Drilling unit / Project number": project_number,
                "Pickup time": pickup_time,
                "Item name": item_name,
                "Projected quantity": projected_q,
                "Taken quantity": taken_q,
                "Returned quantity": returned_q,
                "Comments": comment
            }
            # Build ordered row according to current sheet headers; pad with "" for unknown columns
            new_row = [row_dict.get(h, "") for h in da_headers]

            key = (iid, project_number, order_time)
            if key in existing_map:
                row_index, old_row = existing_map[key]
                # Pad old_row to same length for a fair compare
                old_row = list(old_row) + [""] * (len(da_headers) - len(old_row))

                if old_row != new_row:
                    # update in place
                    update_row("data_analytics", row_index, new_row)
                    existing_map[key] = (row_index, new_row)
                    updated += 1
                else:
                    skipped += 1
            else:
                # append new
                append_row("data_analytics", new_row)
                # newly appended row index = current sheet size + 1 (header) + appended rows so far
                # but we don't strictly need to track it; append-only is fine here
                appended += 1

    return appended, updated, skipped


@data_analytics_bp.route("/data_analytics/export_projects_to_data_analytics", methods=["POST"])
@login_required
@role_required(master_role)
def export_projects_to_data_analytics():
    try:
        appended, updated, skipped = _export_projects_to_data_analytics_job()
        return jsonify({"ok": True, "appended_rows": appended, "updated_rows": updated, "skipped_rows": skipped}), 200
    except Exception as e:
        print("❌ export_projects_to_data_analytics error:", e)
        return jsonify({"ok": False, "error": str(e)}), 500

