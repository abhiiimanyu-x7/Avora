"""
Audit Service - logs every admin action in Avora.
Stores who did what, when, and on which resource.
"""
from datetime import datetime


def get_db():
    from flask import current_app
    return current_app.db


def log_action(admin_id, admin_name, action, target_type, target_id=None, details=None):
    """Record an admin action.

    Args:
        admin_id: ObjectId string of the admin user
        admin_name: Display name of the admin
        action: Short verb phrase, e.g. 'created_election', 'approved_claim'
        target_type: The resource type, e.g. 'election', 'lost_item', 'notice'
        target_id: Optional ObjectId string of the affected resource
        details: Optional dict of extra context
    """
    db = get_db()
    entry = {
        'admin_id': str(admin_id),
        'admin_name': admin_name,
        'action': action,
        'target_type': target_type,
        'target_id': str(target_id) if target_id else None,
        'details': details or {},
        'timestamp': datetime.utcnow(),
    }
    db.audit_log.insert_one(entry)
    return entry


def get_recent_logs(limit=50):
    """Fetch the most recent audit log entries."""
    db = get_db()
    return list(db.audit_log.find().sort('timestamp', -1).limit(limit))


def get_logs_by_admin(admin_id, limit=50):
    """Fetch audit log entries for a specific admin."""
    db = get_db()
    return list(
        db.audit_log.find({'admin_id': str(admin_id)})
        .sort('timestamp', -1)
        .limit(limit)
    )


def get_logs_by_type(target_type, limit=50):
    """Fetch audit log entries for a specific resource type."""
    db = get_db()
    return list(
        db.audit_log.find({'target_type': target_type})
        .sort('timestamp', -1)
        .limit(limit)
    )
