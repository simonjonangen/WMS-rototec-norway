from flask import render_template
import traceback

def register_error_handlers(blueprint):
    @blueprint.app_errorhandler(404)
    def not_found(error):
        print("⚠️ 404 Not Found:", error)
        return render_template('errors/404.html'), 404

    @blueprint.app_errorhandler(500)
    def internal_error(error):
        print("❌ 500 Internal Server Error:", error)
        traceback.print_exc()
        return render_template('errors/500.html'), 500
