from flask import render_template, request, send_file, Blueprint
from app.google_sheets.sheets_service import get_sheet_values
from app.routes.login.login import login_required
from app.routes.shared.utils import role_required
from app.config.roles import ALLOWED_ROLES

import pandas as pd
from io import BytesIO
from datetime import datetime

master_role = ALLOWED_ROLES[1]

issue_logs_bp = Blueprint(
    'issue_logs',
    __name__,
    template_folder='.'
)

@issue_logs_bp.route("/issue_logs", endpoint='issue_logs')
@login_required
@role_required(master_role)
def view_issue_logs():
    try:
        user_filter = request.args.get("user", "").lower()
        article_filter = request.args.get("article", "").lower()

        raw_issues = get_sheet_values("issue_reports", "A1:Z1000")

        expected_headers = [
            "id",
            "issue",
            "article_number",
            "product_name",
            "count",  # ✅ Add count here
            "timestamp",
            "user_name",
            "created_at"
        ]

        issues = []
        if raw_issues and len(raw_issues) > 1:
            headers = raw_issues[0]
            for row in raw_issues[1:]:
                row = row + [""] * (len(expected_headers) - len(row))
                row = row[:len(expected_headers)]
                issue = dict(zip(expected_headers, row))
                issues.append(issue)

        if user_filter:
            issues = [i for i in issues if user_filter in (i.get("user_name") or "").lower()]
        if article_filter:
            issues = [
                r for r in issues
                if article_filter in r.get("article_number", "").lower()
                   or article_filter in r.get("product_name", "").lower()
            ]

        for issue in issues:
            try:
                issue['formatted_timestamp'] = datetime.fromisoformat(issue['timestamp']).strftime('%Y-%m-%d %H:%M')
            except Exception:
                issue['formatted_timestamp'] = issue['timestamp']

        return render_template("issue_logs.html", issues=issues)

    except Exception as e:
        print("❌ Error in /issue_logs:", e)
        return str(e), 500


@issue_logs_bp.route("/export_issue_logs", endpoint="export_issue_logs")
@login_required
@role_required(master_role)
def export_issue_logs():
    try:
        raw_issues = get_sheet_values("issue_reports", "A1:Z1000")

        if not raw_issues or len(raw_issues) < 2:
            return "No issue logs to export.", 400

        headers = raw_issues[0]
        rows = raw_issues[1:]
        df = pd.DataFrame([dict(zip(headers, row)) for row in rows])

        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"issue_logs_export_{timestamp}.xlsx"

        return send_file(output, download_name=filename, as_attachment=True)

    except Exception as e:
        print("❌ Error exporting issue logs:", e)
        return str(e), 500
