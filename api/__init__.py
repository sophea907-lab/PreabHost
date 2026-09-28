from flask import Blueprint
from flask_cors import CORS

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Enable CORS for all API endpoints
CORS(api_bp, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

from . import users
from . import products
