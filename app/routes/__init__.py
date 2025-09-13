from app.routes.home import home_bp  # this imports from __init__.py in home/
from app.routes.shared import shared_bp
from app.routes.take_item import take_item_bp
from app.routes.return_item import return_item_bp
from app.routes.create_project import create_project_bp
from app.routes.catalog import catalog_bp
from app.routes.add_user import add_user_bp
from app.routes.view_users import view_users_bp
from app.routes.logs import logs_bp
from app.routes.user_stats import user_stats_bp
from app.routes.login import login_bp
from app.routes.shared.item_api import item_api_bp
from app.routes.project_logs import project_logs_bp
from app.routes.issue_logs import issue_logs_bp
from app.routes.report_issue import report_issue_bp
from app.routes.catalog import item_bp
from app.routes.projects import projects_bp
from app.routes.data_analytics import data_analytics_bp
from app.routes.add_stock import add_stock_bp


def init_routes(app):
    app.register_blueprint(home_bp, url_prefix='/')  # makes it available at /home
    app.register_blueprint(shared_bp, url_prefix='/')
    app.register_blueprint(take_item_bp, url_prefix='/')
    app.register_blueprint(return_item_bp, url_prefix='/')
    app.register_blueprint(create_project_bp, url_prefix='/')
    app.register_blueprint(catalog_bp, url_prefix='/')
    app.register_blueprint(add_user_bp, url_prefix='/')
    app.register_blueprint(view_users_bp, url_prefix='/')
    app.register_blueprint(logs_bp, url_prefix='/')
    app.register_blueprint(user_stats_bp, url_prefix='/')
    app.register_blueprint(login_bp, url_prefix='/')
    app.register_blueprint(project_logs_bp, url_prefix='/')
    app.register_blueprint(issue_logs_bp, url_prefix='/')
    app.register_blueprint(report_issue_bp, url_prefix='/')
    app.register_blueprint(item_bp, url_prefix='/')
    app.register_blueprint(item_api_bp)
    app.register_blueprint(projects_bp, url_prefix='/')
    app.register_blueprint(data_analytics_bp, url_prefix='/')
    app.register_blueprint(add_stock_bp, url_prefix='/')