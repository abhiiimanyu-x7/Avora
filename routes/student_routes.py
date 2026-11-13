from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from services.election_service import (
    get_all_elections, get_election_by_id, get_candidates,
    get_elections_by_status
)
from services.vote_service import (
    cast_vote, has_voted, get_results, get_user_voting_history,
    get_voter_count, get_participation_rate
)
from services.user_service import get_user_by_id, update_profile, change_student_password
from config import Config

student_bp = Blueprint('student', __name__)


def student_required(f):
    """Decorator to require student login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('user_role') != 'student':
            flash('Please log in as a student to access this page.', 'error')
            return redirect(url_for('auth.student_login'))
        return f(*args, **kwargs)
    return decorated


@student_bp.route('/student/dashboard')
@student_required
def dashboard():
    """Student dashboard campus command center."""
    from services.notices_service import get_upcoming_deadlines, get_active_notices
    from services.lost_found_service import get_all_found_items
    from datetime import datetime

    active = get_elections_by_status('active')
    upcoming = get_elections_by_status('upcoming')
    closed = get_elections_by_status('closed')
    
    # Check vote status for each active election
    for election in active:
        election['has_voted'] = has_voted(session['user_id'], str(election['_id']))
    
    for election in closed:
        election['has_voted'] = has_voted(session['user_id'], str(election['_id']))

    user = get_user_by_id(session['user_id'])
    student_dept = user.get('department') if user else session.get('user_department')
    student_year = user.get('year') if user else session.get('user_year')

    deadlines = get_upcoming_deadlines(limit=5, student_dept=student_dept, student_year=student_year)
    recent_notices = get_active_notices(student_dept=student_dept, student_year=student_year)[:4]
    recent_found = get_all_found_items(status='unclaimed')[:3]

    hour = datetime.now().hour
    if hour < 12:
        greeting_time = "Good morning"
    elif hour < 17:
        greeting_time = "Good afternoon"
    else:
        greeting_time = "Good evening"

    return render_template('student/dashboard.html',
                           active_elections=active,
                           upcoming_elections=upcoming,
                           closed_elections=closed,
                           deadlines=deadlines,
                           recent_notices=recent_notices,
                           recent_found=recent_found,
                           greeting_time=greeting_time)


@student_bp.route('/student/elections')
@student_required
def elections():
    """All elections listing."""
    all_elections = get_all_elections()
    
    for election in all_elections:
        election['has_voted'] = has_voted(session['user_id'], str(election['_id']))
        election['candidate_count'] = len(get_candidates(str(election['_id'])))
        election['voter_count'] = get_voter_count(str(election['_id']))
    
    return render_template('student/elections.html', elections=all_elections)


@student_bp.route('/student/vote/<election_id>', methods=['GET'])
@student_required
def vote_page(election_id):
    """Vote page for a specific election."""
    election = get_election_by_id(election_id)
    if not election:
        flash('Election not found.', 'error')
        return redirect(url_for('student.elections'))
    
    candidates = get_candidates(election_id)
    voted = has_voted(session['user_id'], election_id)
    
    return render_template('student/vote.html',
                           election=election,
                           candidates=candidates,
                           has_voted=voted)


@student_bp.route('/student/vote/<election_id>', methods=['POST'])
@student_required
def cast_vote_route(election_id):
    """Cast a vote (AJAX endpoint)."""
    candidate_id = request.json.get('candidate_id') if request.is_json else request.form.get('candidate_id')
    
    if not candidate_id:
        if request.is_json:
            return jsonify({'success': False, 'message': 'No candidate selected.'}), 400
        flash('No candidate selected.', 'error')
        return redirect(url_for('student.vote_page', election_id=election_id))
    
    success, message = cast_vote(session['user_id'], election_id, candidate_id)
    
    if request.is_json:
        status_code = 200 if success else 400
        return jsonify({'success': success, 'message': message}), status_code
    
    flash(message, 'success' if success else 'error')
    return redirect(url_for('student.vote_page', election_id=election_id))


@student_bp.route('/student/results/<election_id>')
@student_required
def results(election_id):
    """View election results."""
    election = get_election_by_id(election_id)
    if not election:
        flash('Election not found.', 'error')
        return redirect(url_for('student.elections'))
    
    result_data = get_results(election_id)
    voter_count = get_voter_count(election_id)
    participation = get_participation_rate(election_id)
    
    return render_template('student/results.html',
                           election=election,
                           results=result_data['results'],
                           winner=result_data['winner'],
                           total_votes=result_data['total_votes'],
                           voter_count=voter_count,
                           participation_rate=participation)


@student_bp.route('/student/profile', methods=['GET', 'POST'])
@student_required
def profile():
    """Student profile page."""
    user = get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        flash('Session expired or user not found. Please log in again.', 'warning')
        return redirect(url_for('auth.student_login'))
    
    if request.method == 'POST':
        form_type = request.form.get('form_type', '')

        if form_type == 'password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            if not all([current_password, new_password, confirm_password]):
                flash('All password fields are required.', 'error')
            elif new_password != confirm_password:
                flash('New passwords do not match.', 'error')
            else:
                result = change_student_password(session['user_id'], current_password, new_password)
                flash(result['message'], 'success' if result['success'] else 'error')

            return redirect(url_for('student.profile'))
        else:
            flash('Core registration details (name, roll number, department, year) are institutional credentials and cannot be edited by students. Please contact the Registrar office for changes.', 'error')
            return redirect(url_for('student.profile'))

    from services.lost_found_service import get_user_reports, get_user_claims
    from services.notification_service import get_user_notifications
    from services.issue_service import get_user_issues

    voting_history = get_user_voting_history(session['user_id'])
    user_reports = get_user_reports(session['user_id'])
    user_claims = get_user_claims(session['user_id'])
    notifications = get_user_notifications(session['user_id'], limit=10)
    user_issues = get_user_issues(session['user_id'])

    return render_template('student/profile.html',
                           user=user,
                           voting_history=voting_history,
                           user_reports=user_reports,
                           user_claims=user_claims,
                           user_issues=user_issues,
                           notifications=notifications,
                           departments=Config.DEPARTMENTS,
                           years=Config.YEARS)
