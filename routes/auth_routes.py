from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from services.user_service import (
    create_user, authenticate_user, get_user_by_email, get_user_by_roll_no,
    get_db, get_user_by_email_and_role, get_system_setting, reset_user_password
)
from services.email_service import generate_otp, send_otp_email
from config import Config
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)


def _otp_resend_wait(db, email):
    """Return seconds until another code can be sent for this email."""
    record = db.otps.find_one({'email': email}, {'createdAt': 1})
    created_at = record.get('createdAt') if record else None
    if not created_at:
        return 0

    remaining = (
        created_at + timedelta(seconds=Config.OTP_RESEND_SECONDS) - datetime.utcnow()
    ).total_seconds()
    return max(0, int(remaining + 0.999))


def _otp_sent_message():
    """Describe the configured OTP validity period."""
    expiry_seconds = Config.OTP_EXPIRY_SECONDS
    if expiry_seconds < 60:
        duration = f'{expiry_seconds} seconds'
    else:
        minutes = (expiry_seconds + 59) // 60
        duration = f'{minutes} minute' if minutes == 1 else f'{minutes} minutes'
    return f'Verification code sent. It remains valid for {duration}.'


@auth_bp.route('/student/send-otp', methods=['POST'])
def send_otp():
    """Generate and send OTP for registration."""
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    
    allow_any_email = get_system_setting('allow_any_email', False)
    if not allow_any_email and not email.endswith('@kmclu.ac.in'):
        return jsonify({'success': False, 'message': 'Only @kmclu.ac.in institutional emails are allowed.'}), 400
        
    if not email or '@' not in email or '.' not in email.split('@')[-1]:
        return jsonify({'success': False, 'message': 'Please enter a valid email address.'}), 400
        
    if get_user_by_email(email):
        return jsonify({'success': False, 'message': 'An account with this email already exists.'}), 400

    db = get_db()
    resend_wait = _otp_resend_wait(db, email)
    if resend_wait:
        return jsonify({
            'success': False,
            'message': f'Please wait {resend_wait} seconds before requesting another code.',
            'retry_after': resend_wait,
        }), 429

    otp = generate_otp()
    db.otps.update_one(
        {'email': email},
        {'$set': {'otp': otp, 'createdAt': datetime.utcnow()}},
        upsert=True
    )
    
    if send_otp_email(email, otp):
        return jsonify({
            'success': True,
            'message': _otp_sent_message(),
            'expires_in': Config.OTP_EXPIRY_SECONDS,
            'resend_after': Config.OTP_RESEND_SECONDS,
        })
    else:
        return jsonify({'success': False, 'message': 'Failed to send OTP. Please try again.'}), 500


@auth_bp.route('/student/verify-otp', methods=['POST'])
def verify_otp():
    """Verify a registration OTP before it expires."""
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    otp_input = data.get('otp', '').strip()
    
    if not email or not otp_input:
        return jsonify({'success': False, 'message': 'Email and OTP are required.'}), 400
        
    db = get_db()
    otp_record = db.otps.find_one({'email': email})
    if not otp_record or otp_record.get('otp') != otp_input:
        return jsonify({'success': False, 'message': 'Invalid verification code.'}), 400

    created_at = otp_record.get('createdAt')
    if created_at:
        elapsed = (datetime.utcnow() - created_at).total_seconds()
        if elapsed > Config.OTP_EXPIRY_SECONDS:
            return jsonify({'success': False, 'message': 'Verification code has expired. Please request a new one.'}), 400
        
    return jsonify({'success': True, 'message': 'Verification code verified successfully!'})


@auth_bp.route('/student/signup', methods=['GET', 'POST'])
def student_signup():
    """Student registration page."""
    allow_any_email = get_system_setting('allow_any_email', False)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        roll_no = request.form.get('roll_no', '').strip()
        department = request.form.get('department', '')
        year = request.form.get('year', '')
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        otp_input = request.form.get('otp', '').strip()
        
        # Validation
        errors = []
        if not allow_any_email and not email.endswith('@kmclu.ac.in'):
            errors.append('Only @kmclu.ac.in emails are allowed.')
        elif not email or '@' not in email:
            errors.append('Please provide a valid email address.')
        
        required_fields = [name, email, roll_no, department, year, password]
        if not Config.BYPASS_OTP:
            required_fields.append(otp_input)
            
        if not all(required_fields):
            errors.append('All fields are required.')
        
        if not Config.BYPASS_OTP:
            db = get_db()
            otp_record = db.otps.find_one({'email': email})
            if not otp_record or otp_record.get('otp') != otp_input:
                errors.append('Invalid or expired OTP.')
            elif otp_record.get('createdAt'):
                elapsed = (datetime.utcnow() - otp_record['createdAt']).total_seconds()
                if elapsed > Config.OTP_EXPIRY_SECONDS:
                    errors.append('Verification code has expired. Please request a new code.')
                
        if password != confirm_password:
            errors.append('Passwords do not match.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if get_user_by_email(email):
            errors.append('An account with this email already exists.')
        if get_user_by_roll_no(roll_no):
            errors.append('An account with this roll number already exists.')
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('auth/student_signup.html',
                                   departments=Config.DEPARTMENTS,
                                   years=Config.YEARS,
                                   form_data=request.form,
                                   bypass_otp=Config.BYPASS_OTP,
                                   allow_any_email=allow_any_email)
        
        # Create user
        user = create_user({
            'name': name,
            'email': email,
            'roll_no': roll_no,
            'department': department,
            'year': year,
            'password': password,
        })
        
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('auth.student_login'))
    
    return render_template('auth/student_signup.html',
                           departments=Config.DEPARTMENTS,
                           years=Config.YEARS,
                           bypass_otp=Config.BYPASS_OTP,
                           allow_any_email=allow_any_email)


@auth_bp.route('/student/login', methods=['GET', 'POST'])
def student_login():
    """Student login page."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        user = authenticate_user(email, password, role='student')
        
        if user:
            session['user_id'] = str(user['_id'])
            session['user_name'] = user['name']
            session['user_role'] = 'student'
            session['user_department'] = user.get('department', '')
            session['user_year'] = user.get('year', '')
            session['user_email'] = user['email']
            session['user_roll_no'] = user.get('roll_no', '')
            session.permanent = True
            
            flash(f'Welcome back, {user["name"]}!', 'success')
            return redirect(url_for('student.dashboard'))
        else:
            flash('Invalid email or password.', 'error')
            return render_template('auth/student_login.html', form_data=request.form)
    
    return render_template('auth/student_login.html')


@auth_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        user = authenticate_user(email, password, role='admin')
        
        if user:
            session['user_id'] = str(user['_id'])
            session['user_name'] = user['name']
            session['user_role'] = 'admin'
            session['user_email'] = user['email']
            session['is_teacher'] = user.get('is_teacher', False)
            session['admin_scope'] = user.get('admin_scope', 'all')
            session.permanent = True
            
            flash('Welcome to the admin panel.', 'success')
            return redirect(url_for('admin.dashboard'))
        else:
            flash('Invalid credentials.', 'error')
            return render_template('auth/admin_login.html', form_data=request.form)
    
    return render_template('auth/admin_login.html')


# ── Google OAuth Routes ──

@auth_bp.route('/auth/google/login')
def google_login():
    """Redirect to Google for OAuth login (students only)."""
    oauth = current_app.oauth
    redirect_uri = Config.GOOGLE_REDIRECT_URI
    allow_any_email = get_system_setting('allow_any_email', False)
    
    auth_params = {}
    if not allow_any_email:
        auth_params['hd'] = 'kmclu.ac.in'  # Restrict to kmclu.ac.in Google Workspace
        
    return oauth.google.authorize_redirect(
        redirect_uri,
        **auth_params
    )


@auth_bp.route('/auth/google/callback')
def google_callback():
    """Handle Google OAuth callback."""
    oauth = current_app.oauth

    try:
        token = oauth.google.authorize_access_token()
    except Exception:
        flash('Google authentication failed. Please try again.', 'error')
        return redirect(url_for('auth.student_login'))

    user_info = token.get('userinfo')
    if not user_info:
        flash('Could not retrieve your Google account information.', 'error')
        return redirect(url_for('auth.student_login'))

    email = user_info.get('email', '').strip().lower()
    name = user_info.get('name', '')

    allow_any_email = get_system_setting('allow_any_email', False)
    # Enforce @kmclu.ac.in domain if open registration is disabled
    if not allow_any_email and not email.endswith('@kmclu.ac.in'):
        flash('Only @kmclu.ac.in Google accounts are accepted under current university policy.', 'error')
        return redirect(url_for('auth.student_login'))

    # Look up existing student user
    user = get_user_by_email_and_role(email, 'student')

    if not user:
        flash('No account found for this email. Please register first.', 'error')
        return redirect(url_for('auth.student_signup'))

    # Log the student in
    session['user_id'] = str(user['_id'])
    session['user_name'] = user['name']
    session['user_role'] = 'student'
    session['user_department'] = user.get('department', '')
    session['user_year'] = user.get('year', '')
    session['user_email'] = user['email']
    session['user_roll_no'] = user.get('roll_no', '')
    session.permanent = True

    flash(f'Welcome back, {user["name"]}!', 'success')
    return redirect(url_for('student.dashboard'))


@auth_bp.route('/logout')
def logout():
    """Clear session and redirect to landing."""
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('landing'))


# ── Forgot Password Flow ──

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password request and reset page."""
    role = request.args.get('role', 'student').strip().lower()
    if role not in ('student', 'admin'):
        role = 'student'

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        form_role = request.form.get('role', role).strip().lower()
        otp_input = request.form.get('otp', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not email:
            flash('Email address is required.', 'error')
            return render_template('auth/forgot_password.html', role=form_role, email=email)

        if not Config.BYPASS_OTP and not otp_input:
            flash('One-Time Password (OTP) is required.', 'error')
            return render_template('auth/forgot_password.html', role=form_role, email=email)

        if not new_password or len(new_password) < 6:
            flash('New password must be at least 6 characters.', 'error')
            return render_template('auth/forgot_password.html', role=form_role, email=email)

        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('auth/forgot_password.html', role=form_role, email=email)

        # Verify OTP against its configured expiry; resend throttling is separate.
        db = get_db()
        if not Config.BYPASS_OTP:
            otp_record = db.otps.find_one({'email': email})
            if not otp_record or otp_record.get('otp') != otp_input:
                flash('Invalid or expired OTP. Please request a new code.', 'error')
                return render_template('auth/forgot_password.html', role=form_role, email=email)
            elif otp_record.get('createdAt'):
                elapsed = (datetime.utcnow() - otp_record['createdAt']).total_seconds()
                if elapsed > Config.OTP_EXPIRY_SECONDS:
                    flash('Verification code has expired. Please request a new code.', 'error')
                    return render_template('auth/forgot_password.html', role=form_role, email=email)

        # Execute password reset
        result = reset_user_password(email, new_password, role=form_role)
        if result.get('success'):
            db.otps.delete_one({'email': email})
            flash('Password reset successfully! Please sign in with your new password.', 'success')
            if form_role == 'admin':
                return redirect(url_for('auth.admin_login'))
            return redirect(url_for('auth.student_login'))
        else:
            flash(result.get('message', 'Failed to reset password.'), 'error')
            return render_template('auth/forgot_password.html', role=form_role, email=email)

    return render_template('auth/forgot_password.html', role=role, bypass_otp=Config.BYPASS_OTP)


@auth_bp.route('/forgot-password/send-otp', methods=['POST'])
def forgot_password_send_otp():
    """Send OTP for password reset."""
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    role = data.get('role', 'student').strip().lower()

    if not email:
        return jsonify({'success': False, 'message': 'Email address is required.'}), 400
    if role not in ('student', 'admin'):
        return jsonify({'success': False, 'message': 'Choose a valid account type.'}), 400

    db = get_db()
    user = db.users.find_one({'email': email, 'role': role})
    if not user:
        return jsonify({'success': False, 'message': f'No {role} account found matching this email.'}), 404

    resend_wait = _otp_resend_wait(db, email)
    if resend_wait:
        return jsonify({
            'success': False,
            'message': f'Please wait {resend_wait} seconds before requesting another code.',
            'retry_after': resend_wait,
        }), 429

    otp = generate_otp()
    db.otps.update_one(
        {'email': email},
        {'$set': {'otp': otp, 'createdAt': datetime.utcnow()}},
        upsert=True
    )

    if send_otp_email(email, otp, purpose="Password Reset"):
        return jsonify({
            'success': True,
            'message': _otp_sent_message(),
            'expires_in': Config.OTP_EXPIRY_SECONDS,
            'resend_after': Config.OTP_RESEND_SECONDS,
        })
    return jsonify({'success': False, 'message': 'Failed to send verification code. Try again.'}), 500


@auth_bp.route('/forgot-password/verify-otp', methods=['POST'])
def forgot_password_verify_otp():
    """Verify a password reset OTP before it expires."""
    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()
    otp_input = data.get('otp', '').strip()

    if not email or not otp_input:
        return jsonify({'success': False, 'message': 'Email and verification code are required.'}), 400

    db = get_db()
    otp_record = db.otps.find_one({'email': email})
    if not otp_record or otp_record.get('otp') != otp_input:
        return jsonify({'success': False, 'message': 'Invalid verification code.'}), 400

    created_at = otp_record.get('createdAt')
    if created_at:
        elapsed = (datetime.utcnow() - created_at).total_seconds()
        if elapsed > Config.OTP_EXPIRY_SECONDS:
            return jsonify({'success': False, 'message': 'Verification code has expired. Please request a new one.'}), 400

    return jsonify({'success': True, 'message': 'Code verified successfully!'})
