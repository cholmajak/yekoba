from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId
from datetime import datetime
from database import get_db

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            user_role = session.get('role', 'Farm Worker')
            if user_role not in allowed_roles:
                flash('Access denied: You do not have permission to view or perform this action.', 'danger')
                return redirect(url_for('dashboard.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip() # can be username or email
        password = request.form.get('password', '')

        if not identifier or not password:
            flash('Please enter both username/email and password.', 'danger')
            return render_template('auth/login.html', identifier=identifier)

        db = get_db()
        user = db.users.find_one({
            "$or": [
                {"email": identifier.lower()},
                {"username": identifier}
            ]
        })

        if user and check_password_hash(user['password_hash'], password):
            if not user.get('is_active', True):
                flash('Your account has been deactivated. Please contact the Farm Administrator.', 'danger')
                return render_template('auth/login.html')

            # Populate session
            session.clear()
            session['user_id'] = str(user['_id'])
            session['username'] = user['username']
            session['full_name'] = user.get('full_name', user['username'])
            session['email'] = user.get('email', '')
            session['role'] = user.get('role', 'Farm Worker')

            # Update last login
            db.users.update_one(
                {"_id": user['_id']},
                {"$set": {"last_login": datetime.now()}}
            )

            flash(f'Welcome back, {session["full_name"]}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))
        else:
            flash('Invalid username/email or password.', 'danger')

    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))

    db = get_db()
    # Check if this is the very first user (auto-assign Administrator role)
    total_users = db.users.count_documents({})

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        phone = request.form.get('phone', '').strip()
        
        # If first user, make Admin; otherwise default to Farm Worker (or Farm Manager if allowed)
        role = 'Administrator' if total_users == 0 else request.form.get('role', 'Farm Worker')

        errors = []
        if not full_name or not username or not email or not password:
            errors.append('All required fields must be filled.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters long.')
        if password != confirm_password:
            errors.append('Passwords do not match.')

        # Check existing user
        if db.users.find_one({"$or": [{"email": email}, {"username": username}]}):
            errors.append('A user with that email or username already exists.')

        if errors:
            for err in errors:
                flash(err, 'danger')
            return render_template('auth/register.html', 
                                   full_name=full_name, 
                                   username=username, 
                                   email=email, 
                                   phone=phone,
                                   is_first_user=(total_users == 0))

        # Create user
        new_user = {
            "full_name": full_name,
            "username": username,
            "email": email,
            "phone": phone,
            "password_hash": generate_password_hash(password),
            "role": role,
            "is_active": True,
            "created_at": datetime.now(),
            "last_login": None
        }
        res = db.users.insert_one(new_user)

        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', is_first_user=(total_users == 0))

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))
