"""Routes for Digital Wellbeing module."""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from services.wellbeing_service import (
    submit_checkin, get_today_checkin, get_mood_trend, get_streak,
    MOOD_LABELS, MOOD_EMOJIS, COUNSELING_RESOURCES,
)

wellbeing_bp = Blueprint('wellbeing', __name__)


def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('user_role') != 'student':
            flash('Please log in as a student.', 'error')
            return redirect(url_for('auth.student_login'))
        return f(*args, **kwargs)
    return decorated


@wellbeing_bp.route('/wellbeing')
@student_required
def index():
    """Wellbeing check-in page with trend view."""
    today = get_today_checkin(session['user_id'])
    trend = get_mood_trend(session['user_id'], days=30)
    streak = get_streak(session['user_id'])
    return render_template('student/wellbeing.html',
                           today_checkin=today,
                           trend=trend,
                           streak=streak,
                           mood_labels=MOOD_LABELS,
                           mood_emojis=MOOD_EMOJIS,
                           resources=COUNSELING_RESOURCES)


@wellbeing_bp.route('/wellbeing/checkin', methods=['POST'])
@student_required
def checkin():
    """Submit daily mood check-in."""
    mood = request.form.get('mood', '3')
    note = request.form.get('note', '').strip()

    try:
        mood_val = int(mood)
        if mood_val < 1 or mood_val > 5:
            mood_val = 3
    except ValueError:
        mood_val = 3

    submit_checkin(session['user_id'], mood_val, note)
    flash('Check-in recorded.', 'success')
    return redirect(url_for('wellbeing.index'))


@wellbeing_bp.route('/wellbeing/trend-data')
@student_required
def trend_data():
    """JSON endpoint for mood trend chart."""
    trend = get_mood_trend(session['user_id'], days=30)
    data = [{'date': e['date'], 'mood': e['mood']} for e in trend]
    return jsonify(data)
