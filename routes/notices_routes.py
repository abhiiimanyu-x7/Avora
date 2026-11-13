"""Routes for Notices & Deadlines module."""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
from services.notices_service import (
    create_notice, get_all_notices, get_active_notices, get_notice_by_id,
    update_notice, delete_notice, get_upcoming_deadlines,
    get_notice_stats, NOTICE_CATEGORIES,
)
from services.audit_service import log_action
from services.notification_service import broadcast_notification
from services.user_service import get_user_by_id, admin_has_scope

notices_bp = Blueprint('notices', __name__)


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


@notices_bp.route('/notices')
@login_required
def index():
    """Student view of notices & deadlines scoped to their department and year."""
    user = get_user_by_id(session['user_id'])
    student_dept = user.get('department') if user else session.get('user_department')
    student_year = user.get('year') if user else session.get('user_year')
    notices = get_active_notices(student_dept=student_dept, student_year=student_year)
    deadlines = get_upcoming_deadlines(student_dept=student_dept, student_year=student_year)
    return render_template('student/notices.html',
                           notices=notices,
                           deadlines=deadlines,
                           categories=NOTICE_CATEGORIES)


@notices_bp.route('/admin/notices')
@scope_required('notices')
def admin_index():
    """Admin management panel for notices."""
    notices = get_all_notices(include_expired=True)
    stats = get_notice_stats()
    return render_template('admin/notices.html',
                           notices=notices,
                           stats=stats,
                           categories=NOTICE_CATEGORIES)


@notices_bp.route('/admin/notices/create', methods=['POST'])
@scope_required('notices')
def admin_create():
    """Create a new notice with visibility choice."""
    title = request.form.get('title', '').strip()
    body = request.form.get('body', '').strip()
    category = request.form.get('category', 'General')
    deadline = request.form.get('deadline', '').strip() or None
    pinned = request.form.get('pinned') == 'on'
    visibility = request.form.get('visibility', 'all')
    target_departments = request.form.getlist('target_departments')
    target_years = request.form.getlist('target_years')

    if not title:
        flash('Notice title is required.', 'error')
        return redirect(url_for('notices.admin_index'))

    notice = create_notice({
        'title': title,
        'body': body,
        'category': category,
        'deadline': deadline,
        'pinned': pinned,
        'visibility': visibility,
        'target_departments': target_departments,
        'target_years': target_years,
        'created_by': session['user_id'],
        'created_by_name': session.get('user_name', ''),
    })
    log_action(session['user_id'], session.get('user_name', ''), 'created_notice', 'notice', notice['_id'],
               {'title': title, 'visibility': visibility, 'departments': target_departments, 'years': target_years})

    if visibility == 'specific':
        broadcast_notification(
            title, body[:100], 'notices',
            target_departments=target_departments,
            target_years=target_years
        )
    else:
        broadcast_notification(title, body[:100], 'notices')

    flash('Notice posted.', 'success')
    return redirect(url_for('notices.admin_index'))


@notices_bp.route('/admin/notices/<notice_id>/delete', methods=['POST'])
@scope_required('notices')
def admin_delete(notice_id):
    """Delete a notice."""
    delete_notice(notice_id)
    log_action(session['user_id'], session.get('user_name', ''), 'deleted_notice', 'notice', notice_id)
    flash('Notice deleted.', 'success')
    return redirect(url_for('notices.admin_index'))


@notices_bp.route('/admin/notices/<notice_id>/toggle-pin', methods=['POST'])
@scope_required('notices')
def admin_toggle_pin(notice_id):
    """Toggle pin status of a notice."""
    notice = get_notice_by_id(notice_id)
    if notice:
        update_notice(notice_id, {'pinned': not notice.get('pinned', False)})
        flash('Pin status updated.', 'success')
    return redirect(url_for('notices.admin_index'))
