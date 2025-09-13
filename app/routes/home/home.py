from flask import Blueprint, render_template, redirect, url_for, session, flash
import traceback
from app.routes.login.login import login_required  # your custom decorator
from app.config.roles import ALLOWED_ROLES

import os
home_bp = Blueprint(
    'home',
    __name__,
    template_folder='.'  # look for home.html in the same folder as home.py
)


@home_bp.route('/home', endpoint='home')
@login_required
def home():
    try:
        role = session.get('role')
        username = session.get('username')

        if not role or not username:
            flash("⚠️ Please log in to continue.", "warning")
            return redirect(url_for('auth.login'))

        master_role = ALLOWED_ROLES[1]
        print("DEBUG: Session role =", role)

        return render_template('home.html', role=role, allowed_roles=ALLOWED_ROLES,
                               username=username, master_role=master_role)
    except Exception as e:
        print("❌ Error in /home:", e)
        traceback.print_exc()
        return str(e), 400


@home_bp.route('/home_settings', endpoint='home_settings')
@login_required
def home_settings():
    try:
        return render_template('home_settings.html')
    except Exception as e:
        print("❌ Error in /home_settings:", e)
        traceback.print_exc()
        return str(e), 500


@home_bp.route('/home_statistics', endpoint='home_statistics')
@login_required
def home_settings():
    try:
        return render_template('home_statistics.html')
    except Exception as e:
        print("❌ Error in /home_statistics:", e)
        traceback.print_exc()
        return str(e), 500

@home_bp.route('/home_projects', endpoint='home_projects')
@login_required
def home_settings():
    try:
        return render_template('home_projects.html')
    except Exception as e:
        print("❌ Error in /home_projects:", e)
        traceback.print_exc()
        return str(e), 500


