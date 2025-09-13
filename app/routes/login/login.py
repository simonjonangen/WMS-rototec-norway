from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, get_flashed_messages
)
from app.google_sheets.sheets_service import get_user_by_credentials
from functools import wraps
from app.config.roles import ALLOWED_ROLES

# Roles (order assumed: ["worker", "manager"])
worker_role = ALLOWED_ROLES[0].lower()
master_role = ALLOWED_ROLES[1].lower()

login_bp = Blueprint(
    'login',
    __name__,
    template_folder='.',  # current folder
    static_folder='.',    # for script.js or CSS
)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('role') or not session.get('username'):
            flash("⚠️ Please log in to continue.", "warning")
            return redirect(url_for('login.login'))
        return f(*args, **kwargs)
    return decorated_function

@login_bp.route('/')
def index():
    return redirect(url_for('login.login'))

def login_redirect_by_role():
    role = (session.get('role') or "").lower()
    if role == master_role:
        return redirect(url_for('home.home'))        # manager landing
    elif role == worker_role:
        return redirect(url_for('home.home'))  # worker landing (adjust route if needed)
    return redirect(url_for('home.home'))

@login_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or "").strip().lower()
        pin = (request.form.get('pin') or "").strip()

        if not email or not pin:
            flash("❌ Wrong email or pin. Try again.", "danger")
            return render_template('login.html')

        # lookup user by email (case-insensitive) + pin
        user = None
        try:
            user = get_user_by_credentials(email, pin)
        except Exception:
            pass

        if not user:
            flash("❌ Wrong email or pin. Try again.", "danger")
            return render_template('login.html')

        raw_role = (user.get('role') or "").strip().lower()
        if raw_role not in [r.lower() for r in ALLOWED_ROLES]:
            flash("⚠️ Unknown role. Please contact developer.", "danger")
            return render_template('login.html')

        # store normalized values in session
        session['role'] = raw_role
        session['username'] = (user.get('name') or user.get('email') or email).strip()
        session['email'] = (user.get('email') or "").strip().lower()
        session['user_id'] = user.get('id') or user.get('user_id')
        session['is_authenticated'] = True

        return login_redirect_by_role()

    get_flashed_messages()
    return render_template('login.html')

@login_bp.route('/logout')
def logout():
    session.clear()
    flash("✅ Logged out.", "success")
    return redirect(url_for('login.login'))
