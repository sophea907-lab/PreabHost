from flask import Blueprint

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

from auth import login_required, admin_only, super_admin_only
from . import routes
