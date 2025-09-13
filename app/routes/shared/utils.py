from functools import wraps
from flask import session, abort
from app.config.roles import ALLOWED_ROLES
from datetime import datetime
from app.google_sheets.sheets_service import append_row
import logging

def insert_log_entry(article_number, quantity, action, user_name, project_ref):
    log = [
        article_number,
        quantity,
        action,
        user_name,
        project_ref or "",
        datetime.now().isoformat()
    ]
    append_row("logs", [log])
    print(f"📝 Log inserted into Google Sheet: {log}")


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user_role = session.get("role")
            allowed = roles or ALLOWED_ROLES
            if not user_role or user_role not in allowed:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def init_logger():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s'
    )
