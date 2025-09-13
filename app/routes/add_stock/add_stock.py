from flask import Blueprint, render_template, session, send_from_directory
from app.routes.login.login import login_required  # your custom decorator

import os
add_stock_bp = Blueprint(
    'add_stock',
    __name__,
    template_folder='.'  # look for home.html in the same folder as home.py
)


@add_stock_bp.route('/add_stock')
@login_required
def add_stock():
    role = session.get('role')
    return render_template('add_stock.html', role=role)

@add_stock_bp.route('/add_stock_js/<path:filename>')
def add_stock_js(filename):
    return send_from_directory(os.path.dirname(__file__), filename)

