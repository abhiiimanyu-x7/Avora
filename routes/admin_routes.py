from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
from services.election_service import (
    create_election, get_all_elections, get_election_by_id,
    get_candidates, add_candidate, delete_candidate,
    activate_election, close_election, get_election_stats
)
from services.vote_service import (
    get_results, get_voter_count, get_participation_rate, get_recent_votes
)
from services.user_service import (
    get_total_students, change_admin_password, get_user_by_id,
    create_admin_user, get_all_admins, get_user_by_email, admin_has_scope,
    get_system_setting, set_system_setting
)
from services.audit_service import log_action, get_recent_logs
from config import Config

admin_bp = Blueprint('admin', __name__)


def admin_required(f):
    """Decorator to require admin login."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session or session.get('user_role') != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.admin_login'))
        return f(*args, **kwargs)
    return decorated


def scope_required(scope):
    """Decorator factory: require admin to have a specific service scope."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_user_by_id(session.get('user_id'))
            if not admin_has_scope(user, scope):
                flash(f'You do not have access to the {scope} service.', 'error')
                return redirect(url_for('admin.dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator


@admin_bp.route('/admin/dashboard')
@admin_required
def dashboard():
    """Admin dashboard."""
    stats = get_election_stats()
    recent_activity = get_recent_votes(limit=10)
    elections = get_all_elections()
    total_students = get_total_students()
    user = get_user_by_id(session['user_id'])
    recent_logs = get_recent_logs(limit=10)
    
    return render_template('admin/dashboard.html',
                           stats=stats,
                           recent_activity=recent_activity,
                           elections=elections,
                           total_students=total_students,
                           admin_user=user,
                           recent_logs=recent_logs)


@admin_bp.route('/admin/elections')
@admin_required
@scope_required('elections')
def elections():
    """All elections management list."""
    all_elections = get_all_elections()
    
    for election in all_elections:
        election['candidate_count'] = len(get_candidates(str(election['_id'])))
        election['voter_count'] = get_voter_count(str(election['_id']))
    
    return render_template('admin/elections.html', elections=all_elections)


@admin_bp.route('/admin/election/create', methods=['GET', 'POST'])
@admin_required
@scope_required('elections')
def create_election_route():
    """Create a new election with scheduling."""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        post_name = request.form.get('post_name', '').strip()
        description = request.form.get('description', '').strip()
        department = request.form.get('department', 'All Departments')
        start_date = request.form.get('start_date', '')
        end_date = request.form.get('end_date', '')
        scheduled_start = request.form.get('scheduled_start', '').strip() or None
        scheduled_end = request.form.get('scheduled_end', '').strip() or None
        
        if not title or not post_name:
            flash('Title and Post Name are required.', 'error')
            return render_template('admin/create_election.html',
                                   departments=Config.DEPARTMENTS,
                                   form_data=request.form)
        
        election = create_election({
            'title': title,
            'post_name': post_name,
            'description': description,
            'department': department,
            'start_date': start_date,
            'end_date': end_date,
            'scheduled_start': scheduled_start,
            'scheduled_end': scheduled_end,
            'created_by': session['user_id'],
        })
        
        log_action(session['user_id'], session.get('user_name', ''),
                   'created_election', 'election', election['_id'],
                   {'title': title})
        flash('Election created successfully!', 'success')
        return redirect(url_for('admin.elections'))
    
    return render_template('admin/create_election.html',
                           departments=Config.DEPARTMENTS)


@admin_bp.route('/admin/election/<election_id>/candidates', methods=['GET', 'POST'])
@admin_required
@scope_required('elections')
def manage_candidates(election_id):
    """View and add candidates to an election."""
    election = get_election_by_id(election_id)
    if not election:
        flash('Election not found.', 'error')
        return redirect(url_for('admin.elections'))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        roll_no = request.form.get('roll_no', '').strip()
        department = request.form.get('department', '')
        year = request.form.get('year', '')
        manifesto = request.form.get('manifesto', '').strip()
        symbol = request.form.get('symbol', '🗳️').strip()
        
        if not name:
            flash('Candidate name is required.', 'error')
        else:
            add_candidate(election_id, {
                'name': name,
                'roll_no': roll_no,
                'department': department,
                'year': year,
                'manifesto': manifesto,
                'symbol': symbol,
            })
            log_action(session['user_id'], session.get('user_name', ''),
                       'added_candidate', 'election', election_id,
                       {'candidate_name': name})
            flash(f'Candidate "{name}" added successfully!', 'success')
        
        return redirect(url_for('admin.manage_candidates', election_id=election_id))
    
    candidates = get_candidates(election_id)
    
    return render_template('admin/candidates.html',
                           election=election,
                           candidates=candidates,
                           departments=Config.DEPARTMENTS,
                           years=Config.YEARS)


@admin_bp.route('/admin/election/<election_id>/results')
@admin_required
@scope_required('elections')
def election_results(election_id):
    """View election results (admin view with extra stats)."""
    election = get_election_by_id(election_id)
    if not election:
        flash('Election not found.', 'error')
        return redirect(url_for('admin.elections'))
    
    result_data = get_results(election_id)
    voter_count = get_voter_count(election_id)
    participation = get_participation_rate(election_id)
    total_students = get_total_students()
    
    return render_template('admin/results.html',
                           election=election,
                           results=result_data['results'],
                           winner=result_data['winner'],
                           total_votes=result_data['total_votes'],
                           voter_count=voter_count,
                           participation_rate=participation,
                           total_students=total_students)


@admin_bp.route('/admin/election/<election_id>/activate', methods=['POST'])
@admin_required
@scope_required('elections')
def activate_election_route(election_id):
    """Activate an election."""
    election = get_election_by_id(election_id)
    if not election:
        flash('Election not found.', 'error')
        return redirect(url_for('admin.elections'))
    
    if election['status'] != 'upcoming':
        flash('Only upcoming elections can be activated.', 'error')
    else:
        candidates = get_candidates(election_id)
        if len(candidates) < 2:
            flash('An election needs at least 2 candidates to be activated.', 'error')
        else:
            activate_election(election_id)
            log_action(session['user_id'], session.get('user_name', ''),
                       'activated_election', 'election', election_id)
            flash(f'Election "{election["title"]}" is now ACTIVE!', 'success')
    
    return redirect(url_for('admin.elections'))


@admin_bp.route('/admin/election/<election_id>/close', methods=['POST'])
@admin_required
@scope_required('elections')
def close_election_route(election_id):
    """Close an election."""
    election = get_election_by_id(election_id)
    if not election:
        flash('Election not found.', 'error')
        return redirect(url_for('admin.elections'))
    
    if election['status'] != 'active':
        flash('Only active elections can be closed.', 'error')
    else:
        close_election(election_id)
        log_action(session['user_id'], session.get('user_name', ''),
                   'closed_election', 'election', election_id)
        flash(f'Election "{election["title"]}" has been CLOSED.', 'success')
    
    return redirect(url_for('admin.elections'))


@admin_bp.route('/admin/election/<election_id>/candidate/<candidate_id>/delete', methods=['POST'])
@admin_required
@scope_required('elections')
def delete_candidate_route(election_id, candidate_id):
    """Delete a candidate from an election."""
    election = get_election_by_id(election_id)
    if not election:
        flash('Election not found.', 'error')
        return redirect(url_for('admin.elections'))
    
    if election['status'] != 'upcoming':
        flash('Cannot modify candidates of an active or closed election.', 'error')
    else:
        delete_candidate(candidate_id)
        log_action(session['user_id'], session.get('user_name', ''),
                   'deleted_candidate', 'election', election_id)
        flash('Candidate removed.', 'success')
    
    return redirect(url_for('admin.manage_candidates', election_id=election_id))


@admin_bp.route('/admin/profile', methods=['GET', 'POST'])
@admin_required
def profile():
    """Admin profile page with password change."""
    user = get_user_by_id(session['user_id'])
    if not user:
        session.clear()
        flash('Session expired or admin not found. Please log in again.', 'warning')
        return redirect(url_for('auth.admin_login'))

    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not all([current_password, new_password, confirm_password]):
            flash('All password fields are required.', 'error')
            return render_template('admin/profile.html', user=user)

        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return render_template('admin/profile.html', user=user)

        result = change_admin_password(session['user_id'], current_password, new_password)

        if result['success']:
            flash(result['message'], 'success')
            return redirect(url_for('admin.profile'))
        else:
            flash(result['message'], 'error')
            return render_template('admin/profile.html', user=user)

    return render_template('admin/profile.html', user=user)


@admin_bp.route('/admin/change-password', methods=['GET', 'POST'])
@admin_required
def change_password():
    """Redirect to profile page (password change is now part of profile)."""
    return redirect(url_for('admin.profile'))


@admin_bp.route('/admin/manage-admins', methods=['GET', 'POST'])
@admin_required
def manage_admins():
    """Manage admin users (create and list admin users with scoped roles)."""
    user = get_user_by_id(session['user_id'])
    if user.get('admin_scope') != 'all':
        flash('Access denied. Only super administrators can manage admin accounts.', 'error')
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        is_teacher = request.form.get('is_teacher') == 'on' or request.form.get('is_teacher') == 'true'
        admin_scope = request.form.get('admin_scope', 'all')
        
        if admin_scope not in Config.ADMIN_SCOPES:
            admin_scope = 'all'
        
        if not all([name, email, password, confirm_password]):
            flash('All fields are required.', 'error')
        elif password != confirm_password:
            flash('Passwords do not match.', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        elif get_user_by_email(email):
            flash('An account with this email already exists.', 'error')
        else:
            create_admin_user({
                'name': name,
                'email': email,
                'password': password,
                'is_teacher': is_teacher,
                'admin_scope': admin_scope,
            })
            log_action(session['user_id'], session.get('user_name', ''),
                       'created_admin', 'admin', None,
                       {'name': name, 'email': email, 'scope': admin_scope})
            flash('New admin user created successfully!', 'success')
            return redirect(url_for('admin.manage_admins'))
            
    admins = get_all_admins()
    return render_template('admin/manage_admins.html',
                           admins=admins,
                           admin_scopes=Config.ADMIN_SCOPES)


@admin_bp.route('/admin/audit-log')
@admin_required
def audit_log():
    """View the admin audit log."""
    user = get_user_by_id(session['user_id'])
    if user.get('admin_scope') != 'all':
        flash('Access denied.', 'error')
        return redirect(url_for('admin.dashboard'))
    logs = get_recent_logs(limit=100)
    return render_template('admin/audit_log.html', logs=logs)


@admin_bp.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    """Manage platform settings including registration domain policies."""
    user = get_user_by_id(session['user_id'])
    if user.get('admin_scope') != 'all':
        flash('Access denied. Only super administrators can modify system settings.', 'error')
        return redirect(url_for('admin.dashboard'))

    if request.method == 'POST':
        allow_any_email = request.form.get('allow_any_email') == 'on'
        prev_value = get_system_setting('allow_any_email', False)
        
        set_system_setting('allow_any_email', allow_any_email, updated_by=session['user_id'])
        
        log_action(
            session['user_id'],
            session.get('user_name', ''),
            'updated_system_settings',
            'settings',
            None,
            {
                'setting': 'allow_any_email',
                'previous_value': prev_value,
                'new_value': allow_any_email
            }
        )
        
        policy_label = "open to all email addresses" if allow_any_email else "restricted to @kmclu.ac.in institutional emails only"
        flash(f'Registration policy successfully updated: Now {policy_label}.', 'success')
        return redirect(url_for('admin.settings'))

    current_allow_any = get_system_setting('allow_any_email', False)
    return render_template('admin/settings.html',
                           allow_any_email=current_allow_any,
                           admin_user=user)

