import os
from flask import Flask
from datetime import timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import routes setup and utilities
from app.routes import init_routes
from app.routes.shared.utils import init_logger
from app.config import company_name  # ✅ Import your company config

def create_app():
    app = Flask(
        __name__,
        static_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static')),
        template_folder=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
    )

    from jinja2 import ChoiceLoader, FileSystemLoader

    # Point to multiple template folders:
    app.jinja_loader = ChoiceLoader([
        FileSystemLoader(os.path.join(os.path.dirname(__file__), 'routes', 'login')),
        FileSystemLoader(os.path.join(os.path.dirname(__file__), 'routes', 'inventory')),
        FileSystemLoader(os.path.join(os.path.dirname(__file__), 'routes', 'shared')),
        FileSystemLoader(os.path.join(os.path.dirname(__file__), 'routes', 'shared', 'errors')),  # Add this line
    ])

    # 🔐 Secret key and session config
    app.secret_key = os.getenv("SECRET_KEY", "fallback_secret_key")
    app.config['SESSION_PERMANENT'] = True
    app.permanent_session_lifetime = timedelta(days=7)

    init_routes(app)  # This should register inventory_bp

    # ✅ Init logging
    init_logger()

    # 🌐 Inject company name/slogan into all templates
    @app.context_processor
    def inject_company_info():
        return dict(
            COMPANY_NAME=company_name.COMPANY_NAME,
            COMPANY_SLOGAN=company_name.COMPANY_SLOGAN,
            FULL_TITLE=company_name.FULL_TITLE
        )

    # 🔁 No-cache headers
    @app.after_request
    def add_no_cache_headers(response):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    return app
