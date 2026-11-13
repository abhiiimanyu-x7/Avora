"""
Notification Service - shared in-app notification system for Avora.
Notifications are stored per-user and rendered in a bell-icon dropdown.
"""
from datetime import datetime
from bson import ObjectId


def get_db():
    from flask import current_app
    return current_app.db


def create_notification(user_id, title, body, category='info', link=None):
    """Create a notification for a specific user.

    Categories: info, elections, lost_found, notices, wellbeing, contacts
    """
    db = get_db()
    notification = {
        'user_id': str(user_id),
        'title': title,
        'body': body,
        'category': category,
        'link': link,
        'read': False,
        'created_at': datetime.utcnow(),
    }
    result = db.notifications.insert_one(notification)
    notification['_id'] = result.inserted_id
    return notification


def get_user_notifications(user_id, limit=20):
    """Fetch recent notifications for a user, newest first."""
    db = get_db()
    return list(
        db.notifications.find({'user_id': str(user_id)})
        .sort('created_at', -1)
        .limit(limit)
    )


def get_unread_count(user_id):
    """Count unread notifications for a user."""
    db = get_db()
    return db.notifications.count_documents({
        'user_id': str(user_id),
        'read': False,
    })


def mark_as_read(notification_id):
    """Mark a single notification as read."""
    db = get_db()
    db.notifications.update_one(
        {'_id': ObjectId(notification_id)},
        {'$set': {'read': True}},
    )


def mark_all_read(user_id):
    """Mark all notifications for a user as read."""
    db = get_db()
    db.notifications.update_many(
        {'user_id': str(user_id), 'read': False},
        {'$set': {'read': True}},
    )


def broadcast_notification(title, body, category='info', link=None, role='student', target_departments=None, target_years=None):
    """Send a notification to users of a given role, optionally scoped by department and year."""
    db = get_db()
    query = {'role': role}
    if target_departments and 'All' not in target_departments:
        query['department'] = {'$in': target_departments}
    if target_years and 'All' not in target_years:
        query['year'] = {'$in': target_years}

    users = db.users.find(query, {'_id': 1})
    notifications = []
    for user in users:
        notifications.append({
            'user_id': str(user['_id']),
            'title': title,
            'body': body,
            'category': category,
            'link': link,
            'read': False,
            'created_at': datetime.utcnow(),
        })
    if notifications:
        db.notifications.insert_many(notifications)
