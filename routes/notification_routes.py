"""Routes for the shared Notification system."""
from flask import Blueprint, redirect, url_for, session, flash, jsonify
from functools import wraps
from services.notification_service import (
    get_user_notifications, get_unread_count, mark_as_read, mark_all_read,
)

notification_bp = Blueprint('notifications', __name__)


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        return f(*args, **kwargs)
    return decorated


@notification_bp.route('/notifications')
@login_required
def get_notifications():
    """JSON feed of user notifications."""
    notifications = get_user_notifications(session['user_id'])
    data = []
    for n in notifications:
        data.append({
            'id': str(n['_id']),
            'title': n['title'],
            'body': n['body'],
            'category': n.get('category', 'info'),
            'link': n.get('link'),
            'read': n['read'],
            'created_at': n['created_at'].isoformat() if n.get('created_at') else '',
        })
    return jsonify({
        'notifications': data,
        'unread_count': get_unread_count(session['user_id']),
    })


@notification_bp.route('/notifications/read/<notification_id>', methods=['POST'])
@login_required
def read_notification(notification_id):
    """Mark a single notification as read."""
    mark_as_read(notification_id)
    return jsonify({'success': True})


@notification_bp.route('/notifications/read-all', methods=['POST'])
@login_required
def read_all():
    """Mark all notifications as read."""
    mark_all_read(session['user_id'])
    return jsonify({'success': True})
