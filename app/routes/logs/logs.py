from flask import Blueprint, render_template, request, send_file
from app.google_sheets.sheets_service import get_sheet_values
from app.google_sheets.sheets_service import get_all_items
from app.routes.login.login import login_required
from app.routes.shared.utils import role_required
import pandas as pd
from io import BytesIO
from datetime import datetime

from app.config.roles import ALLOWED_ROLES
master_role = ALLOWED_ROLES[1]

logs_bp = Blueprint(
    'logs',
    __name__,
    template_folder='.'
)


@logs_bp.route("/logs", endpoint='logs')
@login_required
def view_logs():
    try:
        user_filter = request.args.get("user", "").lower()
        item_filter = request.args.get("item", "").lower()

        raw_logs = get_sheet_values("logs", "A1:Z1000")

        expected_headers = [
            "id",
            "article_number",
            "quantity",
            "action",
            "user_name",
            "timestamp",
            "status",
            "project_ref"
        ]

        logs = []
        if raw_logs and len(raw_logs) > 1:
            headers = raw_logs[0]
            for row in raw_logs[1:]:
                # Pad or trim rows to match the expected header count
                row = row + [""] * (len(expected_headers) - len(row))
                row = row[:len(expected_headers)]

                # Ensure mapping matches the expected order
                log = dict(zip(expected_headers, row))

                logs.append(log)
        # Fetch all products and map article_number -> product_name
        products = get_all_items()
        article_to_description = {
            item["article_number"]: item.get("product_name", "")
            for item in products
        }

        # Add product_name to each log
        for log in logs:
            log["product_name"] = article_to_description.get(log["article_number"], "Unknown")

        # Apply filters
        if user_filter:
            logs = [l for l in logs if user_filter in (l.get("user_name") or "").lower()]
        if item_filter:
            logs = [
                l for l in logs
                if item_filter in (l.get("article_number") or "").lower()
                   or item_filter in (l.get("product_name") or "").lower()
            ]

        # Sort logs
        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        import pytz  # Add at top of the file

        sweden_tz = pytz.timezone("Europe/Stockholm")  # Swedish timezone

        for log in logs:
            try:
                # Parse original timestamp (assuming it's in UTC)
                utc_dt = datetime.fromisoformat(log['timestamp']).replace(tzinfo=pytz.utc)

                # Convert to Sweden local time
                sweden_dt = utc_dt.astimezone(sweden_tz)

                log['formatted_timestamp'] = sweden_dt.strftime('%Y-%m-%d %H:%M')
            except Exception:
                log['formatted_timestamp'] = log['timestamp']

        # -------------------------------
        # 🔎 Zero Stock Check
        # -------------------------------
        zero_stock_items = [
            item for item in products
            if str(item.get("stock", "0")).strip() in ["0", "0.0", ""]
        ]

        unreturned = []
        if zero_stock_items:
            article_numbers = [item["article_number"] for item in zero_stock_items]
            zero_logs = [log for log in logs if log.get("article_number") in article_numbers]

            log_summary = {}
            for log in zero_logs:
                key = (log["article_number"], log["user_name"])
                qty = int(log.get("quantity", 0))
                if log["action"] == "take":
                    log_summary[key] = log_summary.get(key, 0) + qty
                elif log["action"] == "return":
                    log_summary[key] = log_summary.get(key, 0) - qty

            for (article, user), net_qty in log_summary.items():
                if net_qty > 0:
                    name = article_to_description.get(article, "Unknown")
                    unreturned.append({
                        "article_number": article,
                        "product_name": name,
                        "user": user,
                        "quantity": net_qty
                    })

        return render_template("logs.html", logs=logs, unreturned=unreturned)

    except Exception as e:
        print("❌ Error in /logs:", e)
        return str(e), 500


@logs_bp.route("/export_logs", endpoint="export_logs")
@login_required
@role_required()
def export_logs():
    try:
        raw_logs = get_sheet_values("logs", "A1:Z1000")
        if not raw_logs or len(raw_logs) < 2:
            return "No logs to export.", 400

        headers = raw_logs[0]
        rows = raw_logs[1:]
        df = pd.DataFrame([dict(zip(headers, row)) for row in rows])

        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"logs_export_{timestamp}.xlsx"

        return send_file(output, download_name=filename, as_attachment=True)

    except Exception as e:
        print("❌ Error exporting logs:", e)
        return str(e), 500
