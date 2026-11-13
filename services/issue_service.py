"""
Campus Issues and Grievance Reporting Service - Avora
Admin-verified campus facility, infrastructure, and IT grievance management.
"""
from datetime import datetime
from bson import ObjectId


def get_db():
    from flask import current_app
    return current_app.db


ISSUE_CATEGORIES = [
    'Electrical',
    'Water',
    'Infrastructure',
    'IT',
    'Sanitation',
    'Hostel',
    'Security',
    'Other',
]

ISSUE_STATUSES = [
    'open',
    'in-progress',
    'resolved',
]


def report_issue(data):
    """A student submits a campus issue or grievance."""
    db = get_db()
    category = data.get('category', 'Other')
    if category not in ISSUE_CATEGORIES:
        category = 'Other'

    title = data.get('title', '').strip()
    if not title:
        title = f"{category} Issue at {data.get('location', 'Campus')}"

    now = datetime.utcnow()
    issue = {
        'title': title,
        'category': category,
        'location': data.get('location', '').strip(),
        'description': data.get('description', '').strip(),
        'photo_url': data.get('photo_url'),
        'status': 'open',  # open, in-progress, resolved
        'reported_by': str(data['reported_by']),
        'reporter_name': data.get('reporter_name', ''),
        'reporter_email': data.get('reporter_email', ''),
        'reporter_roll_no': data.get('reporter_roll_no', ''),
        'reporter_department': data.get('reporter_department', ''),
        'admin_remarks': None,
        'triaged_by_id': None,
        'triaged_by_name': None,
        'created_at': now,
        'updated_at': now,
        'resolved_at': None,
    }
    result = db.issues.insert_one(issue)
    issue['_id'] = result.inserted_id
    return issue


def get_all_issues(status=None, category=None, location=None):
    """Retrieve all campus issues with optional filters."""
    db = get_db()
    query = {}
    if status and status != 'all':
        query['status'] = status
    if category and category != 'all':
        query['category'] = category
    if location and location.strip():
        query['location'] = {'$regex': location.strip(), '$options': 'i'}

    return list(db.issues.find(query).sort('created_at', -1))


def get_issue_by_id(issue_id):
    """Retrieve an issue document by ObjectId."""
    db = get_db()
    try:
        return db.issues.find_one({'_id': ObjectId(issue_id)})
    except Exception:
        return None


def get_user_issues(user_id):
    """Retrieve issues submitted by a specific student user."""
    db = get_db()
    return list(db.issues.find({'reported_by': str(user_id)}).sort('created_at', -1))


def update_issue_status(issue_id, status, admin_remarks=None, admin_id=None, admin_name=None):
    """Admin updates an issue status and notes triage remarks."""
    db = get_db()
    if status not in ISSUE_STATUSES:
        return None

    now = datetime.utcnow()
    update_data = {
        'status': status,
        'updated_at': now,
    }
    if admin_remarks is not None:
        update_data['admin_remarks'] = admin_remarks.strip()
    if admin_id:
        update_data['triaged_by_id'] = str(admin_id)
    if admin_name:
        update_data['triaged_by_name'] = admin_name

    if status == 'resolved':
        update_data['resolved_at'] = now
    else:
        update_data['resolved_at'] = None

    try:
        db.issues.update_one(
            {'_id': ObjectId(issue_id)},
            {'$set': update_data}
        )
        return get_issue_by_id(issue_id)
    except Exception:
        return None


def get_hotspot_counts():
    """
    Aggregate counts per category and per location to surface recurring hotspots.
    Also provides high-level triage statistics.
    """
    db = get_db()
    total = db.issues.count_documents({})
    open_count = db.issues.count_documents({'status': 'open'})
    in_progress_count = db.issues.count_documents({'status': 'in-progress'})
    resolved_count = db.issues.count_documents({'status': 'resolved'})

    # Group by category
    category_pipeline = [
        {'$group': {'_id': '$category', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}}
    ]
    raw_cat = list(db.issues.aggregate(category_pipeline))
    by_category = [{'category': item['_id'] or 'Other', 'count': item['count']} for item in raw_cat]

    # Group by location (case-insensitive normalized or trimmed)
    location_pipeline = [
        {'$match': {'location': {'$ne': ''}}},
        {'$group': {'_id': '$location', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 15}
    ]
    raw_loc = list(db.issues.aggregate(location_pipeline))
    by_location = [{'location': item['_id'], 'count': item['count']} for item in raw_loc]

    return {
        'total': total,
        'open': open_count,
        'in_progress': in_progress_count,
        'resolved': resolved_count,
        'by_category': by_category,
        'by_location': by_location,
    }


def get_unique_locations():
    """Get list of distinct locations reported across campus issues."""
    db = get_db()
    locations = db.issues.distinct('location')
    return sorted([loc for loc in locations if loc and loc.strip()])
