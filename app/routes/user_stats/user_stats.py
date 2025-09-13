from flask import Blueprint, render_template
from app.routes.login.login import login_required
from app.routes.shared.utils import role_required
from app.google_sheets.sheets_service import get_sheet_values
from app.google_sheets.sheets_service import get_all_items
from collections import Counter
from app.config.roles import ALLOWED_ROLES

master_role = ALLOWED_ROLES[1]

user_stats_bp = Blueprint(
    'user_stats',
    __name__,
    template_folder='.'
)


# Route: All users list
@user_stats_bp.route('/user_stats')
@login_required
@role_required(master_role)
def user_stats_overview():
    try:
        values = get_sheet_values("logs", "A1:Z1000")
        if not values or len(values) < 2:
            return render_template("user_stats_overview.html", users=[])

        headers = values[0]
        logs = [dict(zip(headers, row)) for row in values[1:] if row]

        users = sorted(set(log['user_name'] for log in logs if log.get('user_name')))
        return render_template("user_stats_overview.html", users=users)

    except Exception as e:
        print("❌ Error in /user_stats:", e)
        return str(e), 500


# Route: Stats for specific user
@user_stats_bp.route('/user_stats/<string:username>')
@login_required
@role_required(master_role)
def user_stats(username):
    try:
        values = get_sheet_values("logs", "A1:Z1000")
        if not values or len(values) < 2:
            return render_template("user_stats.html", stats={}, username=username)

        headers = values[0]
        # Step 1: Parse rows into dicts
        logs = [
            dict(zip(headers, row))
            for row in values[1:]
            if row  # Only skip truly empty rows
        ]

        # Step 2: Filter by username
        logs = [l for l in logs if l.get("user_name") == username]

        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        total_taken = sum(int(log["quantity"]) for log in logs if log["action"] == "take")
        total_returned = sum(int(log["quantity"]) for log in logs if log["action"] == "return")
        last_active = logs[0]["timestamp"][:16].replace("T", " ") if logs else None

        article_counts = Counter(log["article_number"] for log in logs if log.get("article_number"))
        top_articles = article_counts.most_common(5)

        products = get_all_items()
        product_map = {p["article_number"]: p["product_name"] for p in products}

        top_items = [
            {
                "article_number": article,
                "name": product_map.get(article, article),
                "count": count
            }
            for article, count in top_articles
        ]

        from collections import defaultdict

        # Calculate net taken per article_number
        net_quantities = defaultdict(int)
        for log in logs:
            if "article_number" in log and "quantity" in log:
                qty = int(log["quantity"])
                if log["action"] == "take":
                    net_quantities[log["article_number"]] += qty
                elif log["action"] == "return":
                    net_quantities[log["article_number"]] -= qty

        # Filter only items that are still out (net > 0)
        unreturned_items = [
            {
                "article_number": art,
                "name": product_map.get(art, art),
                "quantity": qty
            }
            for art, qty in net_quantities.items()
            if qty > 0
        ]


        stats = {
            "total_taken": total_taken,
            "total_returned": total_returned,
            "last_active": last_active,
            "top_items": top_items,
            "unreturned_items": unreturned_items
        }

        return render_template("user_stats.html", stats=stats, username=username)

    except Exception as e:
        print("❌ Error in /user_stats/<username>:", e)
        return str(e), 500
