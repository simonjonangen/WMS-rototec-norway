from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.utils import secure_filename
from app.routes.login.login import login_required
from app.google_sheets.sheets_service import get_all_items, append_row
import os
import json
import traceback
from datetime import datetime

report_issue_bp = Blueprint(
    'report_issue',
    __name__,
    template_folder='.'
)

@report_issue_bp.route('/report', methods=['GET', 'POST'])
@login_required
def report_issue():
    try:
        if request.method == 'POST':
            article_number = request.form.get("article_number")
            issue_types = request.form.get("issues")
            category = ",".join(json.loads(issue_types)) if issue_types else ""

            note = request.form.get("comment")
            username = session.get("username")
            user_id = session.get("user_id")
            count = request.form.get("count")

            if not article_number or not category:
                flash("⚠️ Item and issue type are required.", "danger")
                return redirect(url_for('report_issue.report_issue'))

            # Optional photo
            photo = request.files.get("photo")
            photo_path = ""
            if photo and photo.filename:
                filename = secure_filename(photo.filename)
                photo_path = os.path.join("static", "uploads", filename)
                photo.save(photo_path)

            # Get article number
            products = get_all_items()
            matched_item = next(
                (item for item in products if str(item["article_number"]) == str(article_number)),
                None
            )

            article_number = matched_item["article_number"] if matched_item else None

            print("🔎 Looking for article:", article_number)
            print("📦 Available articles:", [item["article_number"] for item in products])

            if not matched_item:
                flash("❌ Could not find article number for selected item.", "danger")
                return redirect(url_for('report_issue.report_issue'))

            # Compose issue entry
            now = datetime.now().isoformat()

            product_name = matched_item.get("product_name", "Unknown")

            entry = [
                now.replace(":", "").replace("-", ""),  # rudimentary unique ID
                category,
                article_number,
                product_name,
                str(count),
                now,
                username,
                now
            ]

            append_row("issue_reports", entry)
            print("📝 Issue report logged:", entry)

            flash("✅ Issue reported successfully!", "success")
            return redirect(url_for('home.home'))

        # GET request → render item list
        items = get_all_items()
        role = session.get('role')
        return render_template('report_issue.html', role=role, items=items)

    except Exception as e:
        print("❌ Error in /report:", e)
        traceback.print_exc()
        flash("❌ Failed to submit issue report.", "danger")
        return redirect(url_for('report_issue.report_issue'))


@report_issue_bp.route('/report_issue_js/<path:filename>')
def report_issue_js(filename):
    return send_from_directory(os.path.dirname(__file__), filename)
