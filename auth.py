from functools import wraps
from flask import session, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from models import User

ADMIN_ROLES = ['admin', 'administrator', 'super administrator', 'staff']
SUPER_ADMIN_ROLES = ['admin', 'administrator', 'super administrator']


def hash_password(password: str) -> str:
    """Hash a plaintext password using Werkzeug security."""
    if not password:
        return ""
    return generate_password_hash(password)


def verify_password(stored_password: str, provided_password: str) -> bool:
    """Verify a plaintext password against stored hash or fallback."""
    if not stored_password or not provided_password:
        return False
    try:
        return check_password_hash(stored_password, provided_password)
    except Exception:
        return stored_password == provided_password


def is_authenticated() -> bool:
    """Check if any user session is active."""
    return bool(session.get("user_id"))


def is_admin_user() -> bool:
    """Check if the current session belongs to an authorized admin or staff member."""
    if not is_authenticated():
        return False
    role = (session.get("user_role") or "").lower()
    return role in ADMIN_ROLES


def login_required(view):
    """Decorator requiring an authenticated admin/staff user."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to access the Admin Terminal.", "warning")
            return redirect(url_for("admin.admin_login", next=request.path))
        if not is_admin_user():
            flash("Access denied: Customer accounts cannot access the Admin Portal.", "danger")
            return redirect(url_for("admin.admin_login"))
        return view(*args, **kwargs)
    return wrapped


def admin_only(view):
    """Decorator restricting staff members from sensitive administrative panels."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to access the Admin Terminal.", "warning")
            return redirect(url_for("admin.admin_login", next=request.path))
        if not is_admin_user():
            flash("Access denied: Customer accounts cannot access the Admin Portal.", "danger")
            return redirect(url_for("admin.admin_login"))
        if (session.get("user_role") or "").lower() == "staff":
            flash("Access restricted: Staff members cannot access the User Directory.", "danger")
            return redirect(url_for("admin.admin_dashboard"))
        return view(*args, **kwargs)
    return wrapped


def super_admin_only(view):
    """Decorator restricting access exclusively to Super Administrators / Admins."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to access the Admin Terminal.", "warning")
            return redirect(url_for("admin.admin_login", next=request.path))
        role = (session.get("user_role") or "").lower()
        if role not in SUPER_ADMIN_ROLES:
            flash("Access restricted: Super Administrator privileges required.", "danger")
            return redirect(url_for("admin.admin_dashboard"))
        return view(*args, **kwargs)
    return wrapped


def authenticate_admin(identity: str, password: str):
    """
    Authenticate administrative credentials against Database or preset Super Admin.
    Returns (user_dict_or_obj, None) on success, or (None, error_str) on failure.
    """
    identity = (identity or '').strip()
    if not identity or not password:
        return None, "Please provide both username/email and password."

    user = User.query.filter((User.email == identity) | (User.fullname == identity)).first()

    # Reject customer accounts trying to use admin login
    if user and (user.role or '').lower() == 'customer':
        return None, "Access denied: Customer accounts cannot log in to the Admin Portal. Please use the customer storefront."

    if user and user.check_password(password):
        if (user.role or '').lower() in ADMIN_ROLES:
            return user, None
        return None, "Access denied: Administrative privileges required."

    # Preset Super Administrator fallback
    if identity == 'admin@pspstore.com' and password == 'admin123':
        mock_admin = {
            "id": 9999,
            "fullname": "Sophea Preab",
            "email": "admin@pspstore.com",
            "role": "Super Administrator",
            "image": None
        }
        return mock_admin, None

    return None, "Invalid username or password."
