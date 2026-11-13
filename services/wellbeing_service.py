"""
Digital Wellbeing Service - Avora
Private daily mood check-in with personal trend view.
Never diagnoses. Links to real campus counseling.
"""
from datetime import datetime, timedelta
from bson import ObjectId


def get_db():
    from flask import current_app
    return current_app.db


# Mood scale: 1-5
MOOD_LABELS = {
    1: 'Struggling',
    2: 'Low',
    3: 'Okay',
    4: 'Good',
    5: 'Great',
}

MOOD_EMOJIS = {
    1: '😔',
    2: '😕',
    3: '😐',
    4: '🙂',
    5: '😊',
}


def submit_checkin(user_id, mood, note=''):
    """Record a daily mood check-in. One per day per user."""
    db = get_db()
    today = datetime.utcnow().strftime('%Y-%m-%d')

    # Check if already checked in today
    existing = db.wellbeing_checkins.find_one({
        'user_id': str(user_id),
        'date': today,
    })
    if existing:
        # Update today's entry
        db.wellbeing_checkins.update_one(
            {'_id': existing['_id']},
            {'$set': {'mood': int(mood), 'note': note.strip(), 'updated_at': datetime.utcnow()}},
        )
        return existing
    else:
        checkin = {
            'user_id': str(user_id),
            'mood': int(mood),
            'note': note.strip(),
            'date': today,
            'created_at': datetime.utcnow(),
        }
        result = db.wellbeing_checkins.insert_one(checkin)
        checkin['_id'] = result.inserted_id
        return checkin


def get_today_checkin(user_id):
    """Check if user already checked in today."""
    db = get_db()
    today = datetime.utcnow().strftime('%Y-%m-%d')
    return db.wellbeing_checkins.find_one({
        'user_id': str(user_id),
        'date': today,
    })


def get_mood_trend(user_id, days=30):
    """Get user's mood data for the last N days.
    Returns a list of {date, mood, note} dicts.
    Privacy: this is only ever called for the logged-in user themselves.
    """
    db = get_db()
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%d')
    entries = list(
        db.wellbeing_checkins.find({
            'user_id': str(user_id),
            'date': {'$gte': cutoff},
        }).sort('date', 1)
    )
    return entries


def get_streak(user_id):
    """Calculate consecutive check-in days (streak)."""
    db = get_db()
    entries = list(
        db.wellbeing_checkins.find({'user_id': str(user_id)})
        .sort('date', -1)
        .limit(90)
    )
    if not entries:
        return 0

    streak = 0
    today = datetime.utcnow().date()
    for entry in entries:
        expected = today - timedelta(days=streak)
        entry_date = datetime.strptime(entry['date'], '%Y-%m-%d').date()
        if entry_date == expected:
            streak += 1
        else:
            break
    return streak


# Campus counseling resources (static data, not in DB)
COUNSELING_RESOURCES = [
    {
        'name': 'Student Counseling Center',
        'description': 'Free, confidential counseling for all enrolled students.',
        'phone': 'Check your university directory',
        'hours': 'Mon-Fri, 9:00 AM - 5:00 PM',
    },
    {
        'name': 'Mental Health Helpline',
        'description': 'Vandrevala Foundation 24/7 helpline.',
        'phone': '1860-2662-345',
        'hours': '24/7',
    },
    {
        'name': 'iCall',
        'description': 'TISS psychosocial helpline for students.',
        'phone': '9152987821',
        'hours': 'Mon-Sat, 8 AM - 10 PM',
    },
]
