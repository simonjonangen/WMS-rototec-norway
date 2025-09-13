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


@user_stats_bp.route('/user_stats/<string:username>')
@login_required
@role_required(master_role)
def user_stats(username):
    try:
        values = get_sheet_values("logs", "A1:Z1000")
        if not values or len(values) < 2:
            return render_template("user_stats.html", stats={}, username=username)

        headers = values[0]

        def as_int(v, default=0):
            try:
                return int(str(v).strip())
            except Exception:
                return default

        # 1) Parse rows into dicts (keep even if some cols missing)
        logs = [dict(zip(headers, row)) for row in values[1:] if row]

        # 2) Filter by username
        logs = [l for l in logs if l.get("user_name") == username]

        # 3) Sort newest first (handle missing timestamps)
        logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        # 4) Totals (guard missing keys)
        total_taken = sum(as_int(log.get("quantity")) for log in logs if log.get("action") == "take")
        total_returned = sum(as_int(log.get("quantity")) for log in logs if log.get("action") == "return")
        last_active = logs[0].get("timestamp", "")[:16].replace("T", " ") if logs else None

        # 5) Top articles
        from collections import Counter, defaultdict
        article_counts = Counter(log.get("article_number") for log in logs if log.get("article_number"))
        if None in article_counts:
            del article_counts[None]
        top_articles = article_counts.most_common(5)

        # 6) Product name lookup — SAFE
        products = get_all_items() or []
        product_map = {}
        for p in products:
            art = p.get("article_number")
            # try multiple common name keys; default to ""
            name = p.get("product_name") or p.get("name") or p.get("title") or ""
            if art:
                product_map[art] = name

        top_items = [
            {
                "article_number": article,
                "name": product_map.get(article, article),
                "count": count
            }
            for article, count in top_articles
        ]

        # 7) Compute unreturned items (net > 0)
        net_quantities = defaultdict(int)
        for log in logs:
            art = log.get("article_number")
            if not art:
                continue
            qty = as_int(log.get("quantity"))
            action = log.get("action")
            if action == "take":
                net_quantities[art] += qty
            elif action == "return":
                net_quantities[art] -= qty

        unreturned_items = [
            {
                "article_number": art,
                "name": product_map.get(art, art),
                "quantity": qty
            }
            for art, qty in net_quantities.items() if qty > 0
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
