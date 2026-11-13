"""Routes for Campus Contacts module."""
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from functools import wraps
from services.contacts_service import (
    add_contact, get_all_contacts, get_contact_by_id,
    update_contact, delete_contact, search_contacts,
    CONTACT_CATEGORIES,
)
from services.audit_service import log_action
from services.user_service import get_user_by_id, admin_has_scope

contacts_bp = Blueprint('contacts', __name__)


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


@contacts_bp.route('/contacts')
@login_required
def index():
    """Student view of campus contacts directory."""
    category = request.args.get('category')
    q = request.args.get('q', '').strip()

    if q:
        contacts = search_contacts(q)
    else:
        contacts = get_all_contacts(category=category)

    return render_template('student/contacts.html',
                           contacts=contacts,
                           categories=CONTACT_CATEGORIES,
                           current_category=category,
                           search_query=q)


@contacts_bp.route('/admin/contacts')
@scope_required('contacts')
def admin_index():
    """Admin management panel for contacts."""
    contacts = get_all_contacts()
    return render_template('admin/contacts.html',
                           contacts=contacts,
                           categories=CONTACT_CATEGORIES)


@contacts_bp.route('/admin/contacts/add', methods=['POST'])
@scope_required('contacts')
def admin_add():
    """Add a new contact."""
    name = request.form.get('name', '').strip()
    if not name:
        flash('Contact name is required.', 'error')
        return redirect(url_for('contacts.admin_index'))

    contact = add_contact({
        'name': name,
        'designation': request.form.get('designation', ''),
        'department': request.form.get('department', ''),
        'category': request.form.get('category', 'General'),
        'phone': request.form.get('phone', ''),
        'email': request.form.get('email', ''),
        'office_location': request.form.get('office_location', ''),
        'office_hours': request.form.get('office_hours', ''),
    })
    log_action(session['user_id'], session.get('user_name', ''), 'added_contact', 'contact', contact['_id'],
               {'name': name})
    flash(f'Contact "{name}" added.', 'success')
    return redirect(url_for('contacts.admin_index'))


@contacts_bp.route('/admin/contacts/<contact_id>/delete', methods=['POST'])
@scope_required('contacts')
def admin_delete(contact_id):
    """Delete a contact."""
    delete_contact(contact_id)
    log_action(session['user_id'], session.get('user_name', ''), 'deleted_contact', 'contact', contact_id)
    flash('Contact deleted.', 'success')
    return redirect(url_for('contacts.admin_index'))
