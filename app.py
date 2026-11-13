import os
import sys
import logging
import click
from flask import Flask, render_template, session, jsonify
from pymongo import MongoClient
from werkzeug.security import generate_password_hash
from authlib.integrations.flask_client import OAuth
from config import Config
from datetime import datetime


# ── Structured Logging ──
def _configure_logging(app):
    """Configure structured logging for production."""
    log_level = logging.DEBUG if app.config.get('DEBUG') else logging.INFO

    # Root logger
    root = logging.getLogger()
    root.setLevel(log_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    # Clear existing handlers and add ours
    root.handlers.clear()
    root.addHandler(handler)

    # Suppress noisy library logs (PyMongo heartbeats, etc.)
    logging.getLogger('pymongo').setLevel(logging.INFO)
    if not app.config.get('DEBUG'):
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)

    return logging.getLogger('avora')


db = None
oauth = OAuth()


def create_app():
    global db

    app = Flask(__name__)
    app.config.from_object(Config)

    logger = _configure_logging(app)
    logger.info('Starting Avora application')

    # ── MongoDB Connection (production-appropriate) ──
    mongo_uri = app.config['MONGODB_URI']

    # Validate that secrets are not defaults in production
    if not app.config.get('DEBUG'):
        if app.config['SECRET_KEY'] == 'avora-dev-secret-key-change-me':
            logger.warning('SECRET_KEY is set to default value! Set a strong random key in production.')

    # Connection pooling and retry settings
    client = MongoClient(
        mongo_uri,
        maxPoolSize=20,
        minPoolSize=2,
        maxIdleTimeMS=45000,
        connectTimeoutMS=10000,
        serverSelectionTimeoutMS=10000,
        retryWrites=True,
        retryReads=True,
    )
    try:
        db = client.get_default_database()
        db_name = db.name
    except Exception:
        raw_name = mongo_uri.split('/')[-1].split('?')[0].strip()
        db_name = raw_name if raw_name else 'avora'
        db = client[db_name]
    app.db = db

    # Verify connectivity
    try:
        client.admin.command('ping')
        logger.info('MongoDB connection established: %s', db_name)
    except Exception as e:
        logger.error('MongoDB connection failed: %s', e)

    # ── HTTPS and Proxy Headers (Render uses a reverse proxy) ──
    if not app.config.get('DEBUG'):
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # ── WhiteNoise for production static files ──
    if not app.config.get('DEBUG'):
        try:
            from whitenoise import WhiteNoise
            app.wsgi_app = WhiteNoise(
                app.wsgi_app,
                root=os.path.join(app.root_path, 'static'),
                prefix='static/',
            )
            logger.info('WhiteNoise static file serving enabled')
        except ImportError:
            logger.info('WhiteNoise not installed; using Flask static file serving')

    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=app.config.get('GOOGLE_CLIENT_ID'),
        client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email profile'},
    )
    app.oauth = oauth

    try:
        db.users.create_index('email', unique=True)
        # Drop old non-partial roll_no index if it exists, then create partial filter index
        try:
            idx_info = db.users.index_information()
            if 'roll_no_1' in idx_info and 'partialFilterExpression' not in idx_info['roll_no_1']:
                db.users.drop_index('roll_no_1')
        except Exception:
            pass
        db.users.create_index('roll_no', unique=True, partialFilterExpression={'roll_no': {'$type': 'string'}})
        db.votes.create_index([('user_id', 1), ('election_id', 1)], unique=True)
        db.otps.create_index('createdAt', expireAfterSeconds=app.config['OTP_EXPIRY_SECONDS'])
        db.notifications.create_index([('user_id', 1), ('created_at', -1)])
        db.audit_log.create_index('timestamp', expireAfterSeconds=90 * 24 * 3600)  # 90-day retention
        db.lost_found.create_index('status')
        db.lost_reports.create_index('status')
        db.lost_reports.create_index([('reported_by', 1), ('created_at', -1)])
        db.wellbeing_checkins.create_index([('user_id', 1), ('date', -1)])
        db.notices.create_index([('pinned', -1), ('created_at', -1)])
        db.issues.create_index([('status', 1), ('created_at', -1)])
        db.issues.create_index('reported_by')
        db.settings.create_index('key', unique=True)
    except Exception as e:
        logger.warning('Index creation issue: %s', e)

    # Auto seed default admin (admin@avora.app / Mannu@123 / scope all)
    try:
        existing_admin = db.users.find_one({'email': 'admin@avora.app'})
        if not existing_admin:
            already_seeded = db.settings.find_one({'key': 'admin_seeded'})
            if not already_seeded:
                default_admin = {
                    'name': 'University Administrator',
                    'email': 'admin@avora.app',
                    'roll_no': None,
                    'department': 'Administration',
                    'year': None,
                    'password_hash': generate_password_hash('Mannu@123'),
                    'role': 'admin',
                    'admin_scope': 'all',
                    'created_at': datetime.utcnow(),
                }
                db.users.insert_one(default_admin)
                db.settings.update_one({'key': 'admin_seeded'}, {'$set': {'value': True, 'seeded_at': datetime.utcnow()}}, upsert=True)
                logger.info('Default admin account seeded (admin@avora.app)')
        else:
            db.users.update_one(
                {'email': 'admin@avora.app'},
                {'$set': {
                    'password_hash': generate_password_hash('Mannu@123'),
                    'role': 'admin',
                    'admin_scope': 'all'
                }}
            )
            db.settings.update_one({'key': 'admin_seeded'}, {'$set': {'value': True}}, upsert=True)
    except Exception as e:
        logger.warning('Admin seeding issue: %s', e)

    try:
        db.users.update_many({'role': 'admin', 'admin_scope': {'$exists': False}}, {'$set': {'admin_scope': 'all'}})
    except Exception:
        pass

    # Register blueprints
    from routes.auth_routes import auth_bp
    from routes.student_routes import student_bp
    from routes.admin_routes import admin_bp
    from routes.lost_found_routes import lost_found_bp
    from routes.notices_routes import notices_bp
    from routes.wellbeing_routes import wellbeing_bp
    from routes.contacts_routes import contacts_bp
    from routes.map_routes import map_bp
    from routes.notification_routes import notification_bp
    from routes.ask_avora_routes import ask_avora_bp
    from routes.issue_routes import issue_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(lost_found_bp)
    app.register_blueprint(notices_bp)
    app.register_blueprint(wellbeing_bp)
    app.register_blueprint(contacts_bp)
    app.register_blueprint(map_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(ask_avora_bp)
    app.register_blueprint(issue_bp)

    @app.route('/')
    def landing():
        if 'user_id' in session:
            if session.get('user_role') == 'admin':
                return render_template('landing.html', logged_in=True, role='admin')
            return render_template('landing.html', logged_in=True, role='student')
        return render_template('landing.html', logged_in=False)

    # ── Health Check Endpoint (for Render) ──
    @app.route('/health')
    def health_check():
        """Health check endpoint for Render monitoring."""
        status = {'status': 'ok', 'timestamp': datetime.utcnow().isoformat()}
        try:
            # Quick DB ping
            client.admin.command('ping')
            status['database'] = 'connected'
        except Exception:
            status['database'] = 'disconnected'
            status['status'] = 'degraded'
            return jsonify(status), 503
        return jsonify(status), 200

    @app.context_processor
    def inject_globals():
        from services.notification_service import get_unread_count
        from services.user_service import get_system_setting
        unread = 0
        if 'user_id' in session:
            try:
                unread = get_unread_count(session['user_id'])
            except Exception:
                pass
        return {
            'departments': Config.DEPARTMENTS,
            'years': Config.YEARS,
            'current_year': datetime.now().year,
            'google_login_enabled': bool(Config.GOOGLE_CLIENT_ID),
            'unread_notifications': unread,
            'allow_any_email': get_system_setting('allow_any_email', False),
        }

    # ── Error Handlers (no raw stack traces) ──
    @app.errorhandler(404)
    def not_found(e):
        return render_template('base.html', error=404, error_message='Page not found'), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error('Internal server error: %s', e)
        return render_template('base.html', error=500, error_message='Internal server error'), 500

    @app.errorhandler(429)
    def rate_limited(e):
        return render_template('base.html', error=429, error_message='Too many requests. Please try again later.'), 429

    @app.errorhandler(Exception)
    def handle_unexpected_error(e):
        logger.exception('Unhandled exception: %s', e)
        return render_template('base.html', error=500, error_message='An unexpected error occurred. Please try again.'), 500

    @app.cli.command('seed-admin')
    def seed_admin_cli():
        """Seed or reset the default admin account."""
        db.users.update_one(
            {'email': 'admin@avora.app'},
            {'$set': {
                'name': 'University Administrator',
                'password_hash': generate_password_hash('Mannu@123'),
                'role': 'admin',
                'admin_scope': 'all',
                'created_at': datetime.utcnow(),
            }},
            upsert=True
        )
        db.settings.update_one({'key': 'admin_seeded'}, {'$set': {'value': True}}, upsert=True)
        click.echo('Default admin account (admin@avora.app) seeded successfully.')

    return app


# ── WSGI Application Instance for Gunicorn / Render ──
# Enables both `gunicorn app:app` and `gunicorn "app:create_app()"`
app = create_app()


if __name__ == '__main__':
    app.run(debug=Config.DEBUG, port=5000)