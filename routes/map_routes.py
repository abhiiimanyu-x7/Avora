"""Routes for Campus Map module."""
from flask import Blueprint, render_template, session, flash, redirect, url_for
from functools import wraps
from services.map_service import get_all_buildings, get_building_types

map_bp = Blueprint('campus_map', __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.student_login'))
        return f(*args, **kwargs)
    return decorated


@map_bp.route('/map')
@login_required
def index():
    """Campus map page."""
    buildings = get_all_buildings()
    building_types = get_building_types()
    return render_template('student/map.html',
                           buildings=buildings,
                           building_types=building_types)
