"""Routes for Lost & Found module."""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from functools import wraps
from services.lost_found_service import (
    report_found_item, report_lost_item, get_all_found_items, get_found_item_by_id,
    submit_claim, get_claims_for_item, approve_claim, reject_claim,
    get_user_reports, get_user_claims, check_duplicate_report,
    check_duplicate_lost_report, get_lost_found_stats, get_claim_by_id,
    get_all_items_unified, get_user_lost_reports, get_all_lost_reports,
    close_lost_report, ITEM_CATEGORIES,
)
from services.audit_service import log_action
from services.notification_service import create_notification
from services.user_service import get_user_by_id, admin_has_scope

lost_found_bp = Blueprint('lost_found', __name__)


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


@lost_found_bp.route('/lost-found')
@login_required
def index():
    """Lost & Found listing page with type and category filters."""
    type_filter = request.args.get('type', None)  # 'lost', 'found', or None for all
    category_filter = request.args.get('category', None)
    search_query = request.args.get('q', '').strip()

    # Get unified items
    items = get_all_items_unified(type_filter=type_filter)

    # Apply category filter
    if category_filter:
        items = [i for i in items if i.get('category') == category_filter]

    # Apply search filter
    if search_query:
        q_lower = search_query.lower()
        items = [i for i in items if (
            q_lower in i.get('title', '').lower() or
            q_lower in i.get('description', '').lower() or
            q_lower in i.get('location', '').lower()
        )]

    my_reports = get_user_reports(session['user_id']) if session.get('user_role') == 'student' else []
    my_lost_reports = get_user_lost_reports(session['user_id']) if session.get('user_role') == 'student' else []
    my_claims = get_user_claims(session['user_id']) if session.get('user_role') == 'student' else []

    return render_template('student/lost_found.html',
                           items=items,
                           my_reports=my_reports,
                           my_lost_reports=my_lost_reports,
                           my_claims=my_claims,
                           categories=ITEM_CATEGORIES,
                           current_type=type_filter or 'all',
                           current_category=category_filter or '',
                           search_query=search_query)


@lost_found_bp.route('/lost-found/report', methods=['POST'])
@login_required
def report_item():
    """Submit a found-item report."""
    title = request.form.get('title', '').strip()
    category = request.form.get('category', 'Other')
    description = request.form.get('description', '').strip()
    location_found = request.form.get('location_found', '').strip()
    date_found = request.form.get('date_found', '')
    verification_question = request.form.get('verification_question', '').strip()
    verification_answer = request.form.get('verification_answer', '').strip()

    if not title or not verification_question or not verification_answer:
        flash('Title, verification question, and answer are required.', 'error')
        return redirect(url_for('lost_found.index'))

    if check_duplicate_report(title, category, session['user_id']):
        flash('You already reported a similar item. Check your reports below.', 'warning')
        return redirect(url_for('lost_found.index'))

    report_found_item({
        'title': title,
        'category': category,
        'description': description,
        'location_found': location_found,
        'date_found': date_found,
        'verification_question': verification_question,
        'verification_answer': verification_answer,
        'reported_by': session['user_id'],
        'reporter_name': session.get('user_name', ''),
        'reporter_contact': session.get('user_email', ''),
    })
    flash('Item reported. Others can now claim it.', 'success')
    return redirect(url_for('lost_found.index'))


@lost_found_bp.route('/lost-found/report-lost', methods=['POST'])
@login_required
def report_lost():
    """Submit a lost-item report."""
    title = request.form.get('title', '').strip()
    category = request.form.get('category', 'Other')
    description = request.form.get('description', '').strip()
    location_lost = request.form.get('location_lost', '').strip()
    date_lost = request.form.get('date_lost', '')

    if not title:
        flash('Item name is required.', 'error')
        return redirect(url_for('lost_found.index'))

    if check_duplicate_lost_report(title, category, session['user_id']):
        flash('You already reported a similar lost item. Check your reports below.', 'warning')
        return redirect(url_for('lost_found.index'))

    report_lost_item({
        'title': title,
        'category': category,
        'description': description,
        'location_lost': location_lost,
        'date_lost': date_lost,
        'reported_by': session['user_id'],
        'reporter_name': session.get('user_name', ''),
        'reporter_contact': session.get('user_email', ''),
    })
    flash('Lost item reported. We\'ll notify you if a matching found item appears.', 'success')
    return redirect(url_for('lost_found.index'))


@lost_found_bp.route('/lost-found/close-lost/<report_id>', methods=['POST'])
@login_required
def close_lost(report_id):
    """Close a lost report (user found their item)."""
    from services.lost_found_service import get_lost_report_by_id
    report = get_lost_report_by_id(report_id)
    if not report or report.get('reported_by') != session['user_id']:
        flash('Report not found or access denied.', 'error')
        return redirect(url_for('lost_found.index'))
    close_lost_report(report_id)
    flash('Lost report closed.', 'success')
    return redirect(url_for('lost_found.index'))


@lost_found_bp.route('/lost-found/claim/<item_id>', methods=['POST'])
@login_required
def claim_item(item_id):
    """Submit a claim on a found item."""
    item = get_found_item_by_id(item_id)
    if not item:
        flash('Item not found.', 'error')
        return redirect(url_for('lost_found.index'))

    answer = request.form.get('answer', '').strip()
    if not answer:
        flash('Please answer the verification question.', 'error')
        return redirect(url_for('lost_found.index'))

    submit_claim(item_id, {
        'claimant_id': session['user_id'],
        'claimant_name': session.get('user_name', ''),
        'claimant_contact': session.get('user_email', ''),
        'answer': answer,
    })
    flash('Claim submitted. An admin will review it.', 'success')
    return redirect(url_for('lost_found.index'))


# ── Admin routes ──

@lost_found_bp.route('/admin/lost-found')
@scope_required('lost_found')
def admin_index():
    """Admin moderation panel for Lost & Found."""
    type_filter = request.args.get('type', None)
    found_items = get_all_found_items()
    lost_items = get_all_lost_reports()
    stats = get_lost_found_stats()
    return render_template('admin/lost_found.html',
                           found_items=found_items,
                           lost_items=lost_items,
                           stats=stats,
                           categories=ITEM_CATEGORIES,
                           current_type=type_filter or 'all')


@lost_found_bp.route('/admin/lost-found/<item_id>/claims')
@scope_required('lost_found')
def admin_claims(item_id):
    """View claims for an item."""
    item = get_found_item_by_id(item_id)
    if not item:
        flash('Item not found.', 'error')
        return redirect(url_for('lost_found.admin_index'))
    claims = get_claims_for_item(item_id)
    return render_template('admin/lost_found_claims.html', item=item, claims=claims)


@lost_found_bp.route('/admin/lost-found/claim/<claim_id>/approve', methods=['POST'])
@scope_required('lost_found')
def admin_approve_claim(claim_id):
    """Approve a claim."""
    claim = get_claim_by_id(claim_id)
    approve_claim(claim_id)
    log_action(session['user_id'], session.get('user_name', ''), 'approved_claim', 'lost_found', claim_id)
    if claim:
        create_notification(claim['claimant_id'], 'Claim Approved',
                            'Your lost & found claim has been approved.', 'lost_found')
    flash('Claim approved.', 'success')
    return redirect(url_for('lost_found.admin_index'))


@lost_found_bp.route('/admin/lost-found/claim/<claim_id>/reject', methods=['POST'])
@scope_required('lost_found')
def admin_reject_claim(claim_id):
    """Reject a claim."""
    reject_claim(claim_id)
    log_action(session['user_id'], session.get('user_name', ''), 'rejected_claim', 'lost_found', claim_id)
    flash('Claim rejected.', 'success')
    return redirect(url_for('lost_found.admin_index'))
