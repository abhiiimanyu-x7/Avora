"""
Notices & Deadlines Service - Avora
Admin posts notices with optional deadline dates. Past deadlines auto-expire.
Supports department and academic year audience scoping.
"""
from datetime import datetime
from bson import ObjectId


def get_db():
    from flask import current_app
    return current_app.db


def is_notice_visible_to_student(notice, student_dept=None, student_year=None):
    """
    Check if a notice is visible to a student.
    - If notice visibility is 'all' (or not 'specific'), visible to everyone.
    - If 'specific':
      - If target_departments is specified and not empty:
          if student_dept not in target_departments and 'All' not in target_departments:
              return False
      - If target_years is specified and not empty:
          if student_year not in target_years and 'All' not in target_years:
              return False
      return True
    """
    if not notice:
        return False
    if notice.get('visibility') != 'specific':
        return True

    target_depts = notice.get('target_departments') or []
    target_years = notice.get('target_years') or []

    if target_depts and 'All' not in target_depts:
        if not student_dept or student_dept not in target_depts:
            return False

    if target_years and 'All' not in target_years:
        if not student_year or student_year not in target_years:
            return False

    return True


def create_notice(data):
    """Admin creates a notice, optionally with a deadline and audience scoping."""
    db = get_db()
    visibility = data.get('visibility', 'all')
    if visibility != 'specific':
        visibility = 'all'

    target_departments = data.get('target_departments', [])
    if isinstance(target_departments, str):
        target_departments = [target_departments] if target_departments else []

    target_years = data.get('target_years', [])
    if isinstance(target_years, str):
        target_years = [target_years] if target_years else []

    notice = {
        'title': data['title'].strip(),
        'body': data.get('body', '').strip(),
        'category': data.get('category', 'General'),
        'deadline': data.get('deadline'),  # ISO string or None
        'pinned': data.get('pinned', False),
        'visibility': visibility,  # 'all' or 'specific'
        'target_departments': target_departments,
        'target_years': target_years,
        'created_by': str(data['created_by']),
        'created_by_name': data.get('created_by_name', ''),
        'created_at': datetime.utcnow(),
    }
    result = db.notices.insert_one(notice)
    notice['_id'] = result.inserted_id
    return notice


def get_all_notices(include_expired=False, student_dept=None, student_year=None):
    """Get notices, sorted by pinned first then newest.
    By default hides notices whose deadlines have passed.
    Can be scoped to a specific student's department and year.
    """
    db = get_db()
    notices = list(db.notices.find().sort([('pinned', -1), ('created_at', -1)]))
    now = datetime.utcnow()
    filtered = []
    for n in notices:
        if (student_dept or student_year) and not is_notice_visible_to_student(n, student_dept, student_year):
            continue
        deadline = n.get('deadline')
        if deadline:
            try:
                dl = datetime.fromisoformat(deadline)
                if dl < now:
                    if not include_expired:
                        continue
                    n['expired'] = True
            except (ValueError, TypeError):
                pass
        filtered.append(n)
    return filtered


def get_active_notices(student_dept=None, student_year=None):
    """Get only non-expired notices visible to student."""
    db = get_db()
    notices = list(db.notices.find().sort([('pinned', -1), ('created_at', -1)]))
    now = datetime.utcnow()
    active = []
    for n in notices:
        if (student_dept or student_year) and not is_notice_visible_to_student(n, student_dept, student_year):
            continue
        deadline = n.get('deadline')
        if deadline:
            try:
                dl = datetime.fromisoformat(deadline)
                if dl < now:
                    continue
            except (ValueError, TypeError):
                pass
        active.append(n)
    return active


def get_notice_by_id(notice_id):
    """Get a single notice by ID."""
    db = get_db()
    try:
        return db.notices.find_one({'_id': ObjectId(notice_id)})
    except Exception:
        return None


def update_notice(notice_id, data):
    """Update a notice."""
    db = get_db()
    update_fields = {}
    for field in ['title', 'body', 'category', 'deadline', 'pinned', 'visibility', 'target_departments', 'target_years']:
        if field in data:
            update_fields[field] = data[field]
    if update_fields:
        db.notices.update_one(
            {'_id': ObjectId(notice_id)},
            {'$set': update_fields},
        )
    return get_notice_by_id(notice_id)


def delete_notice(notice_id):
    """Delete a notice."""
    db = get_db()
    try:
        db.notices.delete_one({'_id': ObjectId(notice_id)})
        return True
    except Exception:
        return False


def get_upcoming_deadlines(limit=10, student_dept=None, student_year=None):
    """Get notices with upcoming deadlines, soonest first."""
    db = get_db()
    now = datetime.utcnow().isoformat()
    query_limit = limit * 3 if (student_dept or student_year) else limit
    notices = list(db.notices.find({
        'deadline': {'$ne': None, '$gt': now},
    }).sort('deadline', 1).limit(query_limit))

    if student_dept or student_year:
        filtered = [n for n in notices if is_notice_visible_to_student(n, student_dept, student_year)]
        return filtered[:limit]
    return notices[:limit]


def get_notice_stats():
    """Stats for admin dashboard."""
    db = get_db()
    total = db.notices.count_documents({})
    now = datetime.utcnow().isoformat()
    with_deadlines = db.notices.count_documents({'deadline': {'$ne': None}})
    return {
        'total': total,
        'with_deadlines': with_deadlines,
    }


NOTICE_CATEGORIES = [
    'General',
    'Academic',
    'Examinations',
    'Events',
    'Administrative',
    'Sports',
    'Library',
    'Hostel',
    'Placement',
    'Scholarship',
]
