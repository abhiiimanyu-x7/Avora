"""Routes for Campus Issues and Grievance Reporting module."""
import os
import uuid
from functools import wraps
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash, current_app
)
from werkzeug.utils import secure_filename

from services.issue_service import (
    report_issue, get_all_issues, get_issue_by_id,
    get_user_issues, update_issue_status, get_hotspot_counts,
    get_unique_locations, ISSUE_CATEGORIES, ISSUE_STATUSES
)
from services.audit_service import log_action
from services.notification_service import create_notification
from services.user_service import get_user_by_id, admin_has_scope

issue_bp = Blueprint('issues', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'gif'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.student_login'))
        return f(*args, **kwargs)
    return decorated


def scope_required(scope):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session or session.get('user_role') != 'admin':
                flash('Admin access required.', 'error')
                return redirect(url_for('auth.admin_login'))
            user = get_user_by_id(session.get('user_id'))
            if not admin_has_scope(user, scope):
                flash(f'You do not have access to the {scope} service.', 'error')
                return redirect(url_for('admin.dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator


@issue_bp.route('/issues')
@login_required
def index():
    """Student view for campus issue and grievance reporting."""
    user = get_user_by_id(session['user_id'])
    my_issues = get_user_issues(session['user_id'])
    campus_issues = get_all_issues()
    
    return render_template(
        'student/issues.html',
        categories=ISSUE_CATEGORIES,
        my_issues=my_issues,
        campus_issues=campus_issues,
        user=user
    )


@issue_bp.route('/issues/report', methods=['POST'])
@login_required
def submit_report():
    """Submit a new campus facility or infrastructure issue."""
    title = request.form.get('title', '').strip()
    category = request.form.get('category', 'Other')
    location = request.form.get('location', '').strip()
    description = request.form.get('description', '').strip()

    if not location or not description:
        flash('Location and description are required to submit an issue report.', 'error')
        return redirect(url_for('issues.index'))

    photo_url = None
    if 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            safe_name = secure_filename(file.filename)
            unique_name = f"{uuid.uuid4().hex[:12]}_{safe_name}"
            upload_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'issues')
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, unique_name)
            file.save(file_path)
            photo_url = f"/static/uploads/issues/{unique_name}"

    user = get_user_by_id(session['user_id'])
    reporter_name = session.get('user_name', '')
    reporter_email = session.get('user_email', '')
    reporter_roll_no = session.get('user_roll_no', '')
    reporter_department = session.get('user_department', '')

    if user:
        reporter_name = user.get('name', reporter_name)
        reporter_email = user.get('email', reporter_email)
        reporter_roll_no = user.get('roll_no', reporter_roll_no)
        reporter_department = user.get('department', reporter_department)

    report_issue({
        'title': title,
        'category': category,
        'location': location,
        'description': description,
        'photo_url': photo_url,
        'reported_by': session['user_id'],
        'reporter_name': reporter_name,
        'reporter_email': reporter_email,
        'reporter_roll_no': reporter_roll_no,
        'reporter_department': reporter_department,
    })

    flash('Campus issue reported successfully. Facilities administration will review and triage.', 'success')
    return redirect(url_for('issues.index'))


# ── Admin Routes ──

@issue_bp.route('/admin/issues')
@scope_required('issues')
def admin_index():
    """Admin dashboard for triaging campus issues and hotspot analytics."""
    status = request.args.get('status', 'all')
    category = request.args.get('category', 'all')
    location_q = request.args.get('location', '').strip()

    issues = get_all_issues(status=status, category=category, location=location_q)
    hotspots = get_hotspot_counts()
    unique_locations = get_unique_locations()

    return render_template(
        'admin/issues.html',
        issues=issues,
        hotspots=hotspots,
        categories=ISSUE_CATEGORIES,
        statuses=ISSUE_STATUSES,
        selected_status=status,
        selected_category=category,
        location_q=location_q,
        unique_locations=unique_locations
    )


@issue_bp.route('/admin/issues/<issue_id>/status', methods=['POST'])
@scope_required('issues')
def admin_update_status(issue_id):
    """Admin updates the status and remarks for a reported issue."""
    issue = get_issue_by_id(issue_id)
    if not issue:
        flash('Issue record not found.', 'error')
        return redirect(url_for('issues.admin_index'))

    new_status = request.form.get('status', '').strip().lower()
    admin_remarks = request.form.get('admin_remarks', '').strip()

    if new_status not in ISSUE_STATUSES:
        flash('Invalid status provided.', 'error')
        return redirect(url_for('issues.admin_index'))

    updated = update_issue_status(
        issue_id=issue_id,
        status=new_status,
        admin_remarks=admin_remarks,
        admin_id=session.get('user_id'),
        admin_name=session.get('user_name', 'Admin')
    )

    log_action(
        admin_id=session['user_id'],
        admin_name=session.get('user_name', 'Admin'),
        action=f'updated_issue_status_{new_status}',
        target_type='issue',
        target_id=issue_id,
        details={'status': new_status, 'remarks': admin_remarks}
    )

    # In-app notification to reporting student
    create_notification(
        user_id=issue['reported_by'],
        title=f"Grievance Status: {new_status.replace('-', ' ').title()}",
        body=f"Your report '{issue['title']}' has been updated to {new_status.replace('-', ' ').title()}. Remarks: {admin_remarks or 'None provided.'}",
        category='info',
        link=url_for('issues.index')
    )

    flash(f"Issue status updated to {new_status.replace('-', ' ').title()}.", 'success')
    return redirect(url_for('issues.admin_index'))
