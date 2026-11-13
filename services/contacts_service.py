"""
Campus Contacts Service - Avora
Admin-maintained directory of campus offices, departments, and people.
"""
from datetime import datetime
from bson import ObjectId


def get_db():
    from flask import current_app
    return current_app.db


def add_contact(data):
    """Add a new campus contact."""
    db = get_db()
    contact = {
        'name': data['name'].strip(),
        'designation': data.get('designation', '').strip(),
        'department': data.get('department', '').strip(),
        'category': data.get('category', 'General'),
        'phone': data.get('phone', '').strip(),
        'email': data.get('email', '').strip().lower(),
        'office_location': data.get('office_location', '').strip(),
        'office_hours': data.get('office_hours', '').strip(),
        'created_at': datetime.utcnow(),
    }
    result = db.campus_contacts.insert_one(contact)
    contact['_id'] = result.inserted_id
    return contact


def get_all_contacts(category=None):
    """Get all contacts, optionally filtered by category."""
    db = get_db()
    query = {}
    if category:
        query['category'] = category
    return list(db.campus_contacts.find(query).sort('name', 1))


def get_contact_by_id(contact_id):
    """Get a single contact by ID."""
    db = get_db()
    try:
        return db.campus_contacts.find_one({'_id': ObjectId(contact_id)})
    except Exception:
        return None


def update_contact(contact_id, data):
    """Update a contact."""
    db = get_db()
    update_fields = {}
    for field in ['name', 'designation', 'department', 'category', 'phone', 'email', 'office_location', 'office_hours']:
        if field in data:
            val = data[field]
            if field == 'email' and val:
                val = val.strip().lower()
            elif isinstance(val, str):
                val = val.strip()
            update_fields[field] = val
    if update_fields:
        db.campus_contacts.update_one(
            {'_id': ObjectId(contact_id)},
            {'$set': update_fields},
        )
    return get_contact_by_id(contact_id)


def delete_contact(contact_id):
    """Delete a contact."""
    db = get_db()
    try:
        db.campus_contacts.delete_one({'_id': ObjectId(contact_id)})
        return True
    except Exception:
        return False


def search_contacts(query_text):
    """Search contacts by name, department, or designation."""
    db = get_db()
    regex = {'$regex': query_text, '$options': 'i'}
    return list(db.campus_contacts.find({
        '$or': [
            {'name': regex},
            {'department': regex},
            {'designation': regex},
        ]
    }).sort('name', 1))


CONTACT_CATEGORIES = [
    'Administration',
    'Academic',
    'Student Services',
    'Library',
    'Hostel',
    'Sports',
    'Health & Medical',
    'Placement Cell',
    'Accounts & Finance',
    'IT & Technical',
    'Security',
    'Other',
]
