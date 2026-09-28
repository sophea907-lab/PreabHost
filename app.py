from flask import Flask, render_template, request, flash, redirect, jsonify
from config import Config
from extension import db, migrate, csrf, limiter, cors
from admin import admin_bp, login_required, admin_only
from front import front_bp, orders, users
from api import api_bp
from flask_wtf.csrf import CSRFError

app = Flask(__name__)
app.config.from_object(Config)

# Initialize Extensions
db.init_app(app)
migrate.init_app(app, db)
csrf.init_app(app)
limiter.init_app(app)
cors.init_app(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# Exempt REST API from CSRF protection
csrf.exempt(api_bp)

with app.app_context():
    db.create_all()

# Register Blueprints
app.register_blueprint(front_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)


# Error Handlers for CSRF & Rate Limiting
@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    if request.path.startswith('/api/'):
        return jsonify({"error": "CSRF validation error", "reason": e.description}), 400
    flash("Security token expired or invalid. Please try submitting again.", "warning")
    return redirect(request.referrer or request.url)


@app.errorhandler(429)
def ratelimit_handler(e):
    if request.path.startswith('/api/') or request.is_json:
        return jsonify({"error": "Rate limit exceeded", "message": str(e.description)}), 429
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Too Many Requests - PSPSTORE</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-50 min-h-screen flex items-center justify-center p-6 text-slate-800 font-sans">
        <div class="max-w-md w-full bg-white rounded-3xl p-8 border border-slate-200 shadow-xl text-center space-y-4">
            <div class="w-16 h-16 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center mx-auto">
                <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
            </div>
            <h1 class="text-2xl font-black text-slate-900">Too Many Requests</h1>
            <p class="text-sm text-slate-500">Rate limit exceeded: {e.description}. Please wait a moment before trying again.</p>
            <div class="pt-2">
                <button onclick="window.history.back()" class="px-5 py-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-xs font-bold transition-all shadow-md">Go Back</button>
            </div>
        </div>
    </body>
    </html>
    """, 429


if __name__ == '__main__':
    app.run(debug=True)
