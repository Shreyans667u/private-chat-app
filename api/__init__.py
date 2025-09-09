# api/__init__.py
from flask import Blueprint

# Create a blueprint for API routes
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Import routes
from . import group_routes
