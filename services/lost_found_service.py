"""
Lost & Found Service - Avora
Admin-verified lost-and-found system with verification questions.
"""
from datetime import datetime
from bson import ObjectId


def get_db():
    from flask import current_app
    return current_app.db


def report_found_item(data):
    """A finder reports an item they found. They set verification questions."""
    db = get_db()
    item = {
        'title': data['title'].strip(),
        'description': data.get('description', '').strip(),
        'location_found': data.get('location_found', '').strip(),
        'category': data.get('category', 'Other'),
        'date_found': data.get('date_found', ''),
        'reported_by': str(data['reported_by']),
        'reporter_name': data.get('reporter_name', ''),
        'reporter_contact': data.get('reporter_contact', ''),
        'verification_question': data.get('verification_question', '').strip(),
        'verification_answer': data.get('verification_answer', '').strip().lower(),
        'status': 'unclaimed',  # unclaimed, claim_pending, claimed, returned
        'created_at': datetime.utcnow(),
    }
    result = db.lost_found.insert_one(item)
    item['_id'] = result.inserted_id
    return item


def report_lost_item(data):
    """A student reports an item they lost."""
    db = get_db()
    item = {
        'title': data['title'].strip(),
        'description': data.get('description', '').strip(),
        'location_lost': data.get('location_lost', '').strip(),
        'category': data.get('category', 'Other'),
        'date_lost': data.get('date_lost', ''),
        'reported_by': str(data['reported_by']),
        'reporter_name': data.get('reporter_name', ''),
        'reporter_contact': data.get('reporter_contact', ''),
        'type': 'lost',
        'status': 'open',  # open, matched, closed
        'created_at': datetime.utcnow(),
    }
    result = db.lost_reports.insert_one(item)
    item['_id'] = result.inserted_id
    return item


def check_duplicate_lost_report(title, category, user_id):
    """Check if this user already reported a similar lost item."""
    db = get_db()
    existing = db.lost_reports.find_one({
        'reported_by': str(user_id),
        'title': {'$regex': title.strip(), '$options': 'i'},
        'category': category,
        'status': 'open',
    })
    return existing is not None


def get_all_lost_reports(status=None):
    """Get all lost item reports, optionally filtered by status."""
    db = get_db()
    query = {}
    if status:
        query['status'] = status
    return list(db.lost_reports.find(query).sort('created_at', -1))


def get_all_items_unified(type_filter=None, status_filter=None):
    """Get a unified list of both lost and found items for the listing view.

    Args:
        type_filter: 'lost', 'found', or None for all.
        status_filter: Filter by status string, or None for all.

    Returns:
        List of item dicts with a normalised 'type' field added.
    """
    items = []

    # Include found items
    if type_filter is None or type_filter == 'found':
        found_query = {}
        if status_filter:
            found_query['status'] = status_filter
        else:
            found_query['status'] = 'unclaimed'  # default: only show unclaimed
        found_items = list(get_db().lost_found.find(found_query).sort('created_at', -1))
        for fi in found_items:
            fi['type'] = 'found'
            fi['location'] = fi.get('location_found', '')
            fi['date'] = fi.get('date_found', '')
        items.extend(found_items)

    # Include lost items
    if type_filter is None or type_filter == 'lost':
        lost_query = {}
        if status_filter:
            lost_query['status'] = status_filter
        else:
            lost_query['status'] = 'open'
        lost_items = list(get_db().lost_reports.find(lost_query).sort('created_at', -1))
        for li in lost_items:
            li['type'] = 'lost'
            li['location'] = li.get('location_lost', '')
            li['date'] = li.get('date_lost', '')
        items.extend(lost_items)

    # Sort combined list by created_at descending
    items.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
    return items


def check_duplicate_report(title, category, user_id):
    """Check if this user already reported a similar found item."""
    db = get_db()
    existing = db.lost_found.find_one({
        'reported_by': str(user_id),
        'title': {'$regex': title.strip(), '$options': 'i'},
        'category': category,
        'status': 'unclaimed',
    })
    return existing is not None


def get_lost_report_by_id(report_id):
    """Get a single lost report by ID."""
    db = get_db()
    try:
        return db.lost_reports.find_one({'_id': ObjectId(report_id)})
    except Exception:
        return None


def close_lost_report(report_id):
    """Close a lost report (e.g. owner found the item themselves)."""
    db = get_db()
    db.lost_reports.update_one(
        {'_id': ObjectId(report_id)},
        {'$set': {'status': 'closed'}},
    )


def get_all_found_items(status=None):
    """Get all found items, optionally filtered by status."""
    db = get_db()
    query = {}
    if status:
        query['status'] = status
    return list(db.lost_found.find(query).sort('created_at', -1))


def get_found_item_by_id(item_id):
    """Get a single found item by ID."""
    db = get_db()
    try:
        return db.lost_found.find_one({'_id': ObjectId(item_id)})
    except Exception:
        return None


def submit_claim(item_id, claimant_data):
    """A student submits a claim on a found item with their answer."""
    db = get_db()
    claim = {
        'item_id': str(item_id),
        'claimant_id': str(claimant_data['claimant_id']),
        'claimant_name': claimant_data.get('claimant_name', ''),
        'claimant_contact': claimant_data.get('claimant_contact', ''),
        'answer': claimant_data.get('answer', '').strip().lower(),
        'status': 'pending',  # pending, approved, rejected
        'submitted_at': datetime.utcnow(),
    }
    result = db.claims.insert_one(claim)
    claim['_id'] = result.inserted_id

    # Update item status
    db.lost_found.update_one(
        {'_id': ObjectId(item_id)},
        {'$set': {'status': 'claim_pending'}},
    )
    return claim


def get_claims_for_item(item_id):
    """Get all claims for a specific found item."""
    db = get_db()
    return list(db.claims.find({'item_id': str(item_id)}).sort('submitted_at', -1))


def get_claim_by_id(claim_id):
    """Get a single claim by ID."""
    db = get_db()
    try:
        return db.claims.find_one({'_id': ObjectId(claim_id)})
    except Exception:
        return None


def approve_claim(claim_id):
    """Admin approves a claim."""
    db = get_db()
    claim = get_claim_by_id(claim_id)
    if not claim:
        return False
    db.claims.update_one(
        {'_id': ObjectId(claim_id)},
        {'$set': {'status': 'approved'}},
    )
    # Reject other pending claims for the same item
    db.claims.update_many(
        {'item_id': claim['item_id'], '_id': {'$ne': ObjectId(claim_id)}, 'status': 'pending'},
        {'$set': {'status': 'rejected'}},
    )
    # Mark item as claimed
    db.lost_found.update_one(
        {'_id': ObjectId(claim['item_id'])},
        {'$set': {'status': 'claimed'}},
    )
    return True


def reject_claim(claim_id):
    """Admin rejects a claim."""
    db = get_db()
    claim = get_claim_by_id(claim_id)
    if not claim:
        return False
    db.claims.update_one(
        {'_id': ObjectId(claim_id)},
        {'$set': {'status': 'rejected'}},
    )
    # If no more pending claims, set item back to unclaimed
    remaining = db.claims.count_documents({
        'item_id': claim['item_id'],
        'status': 'pending',
    })
    if remaining == 0:
        db.lost_found.update_one(
            {'_id': ObjectId(claim['item_id'])},
            {'$set': {'status': 'unclaimed'}},
        )
    return True


def get_user_reports(user_id):
    """Get all found-item reports by a specific user."""
    db = get_db()
    return list(db.lost_found.find({'reported_by': str(user_id)}).sort('created_at', -1))


def get_user_lost_reports(user_id):
    """Get all lost-item reports by a specific user."""
    db = get_db()
    return list(db.lost_reports.find({'reported_by': str(user_id)}).sort('created_at', -1))


def get_user_claims(user_id):
    """Get all claims submitted by a specific user."""
    db = get_db()
    claims = list(db.claims.find({'claimant_id': str(user_id)}).sort('submitted_at', -1))
    for claim in claims:
        claim['item'] = get_found_item_by_id(claim['item_id'])
    return claims


def get_lost_found_stats():
    """Aggregate stats for admin dashboard."""
    db = get_db()
    return {
        'total_found': db.lost_found.count_documents({}),
        'unclaimed': db.lost_found.count_documents({'status': 'unclaimed'}),
        'claimed': db.lost_found.count_documents({'status': 'claimed'}),
        'pending_claims': db.claims.count_documents({'status': 'pending'}),
        'total_lost': db.lost_reports.count_documents({}),
        'open_lost': db.lost_reports.count_documents({'status': 'open'}),
    }


ITEM_CATEGORIES = [
    'Electronics',
    'Books & Notes',
    'ID Cards & Documents',
    'Clothing',
    'Water Bottles',
    'Keys',
    'Bags & Wallets',
    'Stationery',
    'Other',
]
