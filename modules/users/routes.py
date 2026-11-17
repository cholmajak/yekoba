from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash
from bson import ObjectId
from datetime import datetime
from database import get_db
from modules.auth import login_required, role_required

users_bp = Blueprint('users', __name__, url_prefix='/users')

ROLES = ['Administrator', 'Farm Manager', 'Farm Worker']

@users_bp.route('/')
@login_required
@role_required(['Administrator'])
def index():
    db = get_db()
    users = list(db.users.find().sort("created_at", -1))
    return render_template('users/index.html', users=users, roles=ROLES)

@users_bp.route('/add', methods=['POST'])
@login_required
@role_required(['Administrator'])
def add():
    db = get_db()
    full_name = request.form.get('full_name', '').strip()
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip().lower()
    role = request.form.get('role', 'Farm Worker')
    password = request.form.get('password', 'FarmPass123!')
    phone = request.form.get('phone', '').strip()

    if not full_name or not username or not email:
        flash('Full Name, Username, and Email are required.', 'danger')
        return redirect(url_for('users.index'))

    if db.users.find_one({"$or": [{"email": email}, {"username": username}]}):
        flash('A user with that username or email already exists.', 'danger')
        return redirect(url_for('users.index'))

    new_user = {
        "full_name": full_name,
        "username": username,
        "email": email,
        "phone": phone,
        "role": role,
        "password_hash": generate_password_hash(password),
        "is_active": True,
        "created_at": datetime.now(),
        "last_login": None
    }
    db.users.insert_one(new_user)

    flash(f'User "{username}" created successfully with role "{role}".', 'success')
    return redirect(url_for('users.index'))

@users_bp.route('/edit-role/<user_id>', methods=['POST'])
@login_required
@role_required(['Administrator'])
def edit_role(user_id):
    db = get_db()
    new_role = request.form.get('role')
    is_active = request.form.get('is_active') == 'true'

    try:
        # Prevent deactivating self
        if str(user_id) == session.get('user_id'):
            flash('You cannot modify your own administrator permissions or deactivate your own account.', 'warning')
            return redirect(url_for('users.index'))

        db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"role": new_role, "is_active": is_active, "updated_at": datetime.now()}}
        )
        flash('User account updated.', 'success')
    except Exception as e:
        flash(f'Error updating user: {e}', 'danger')

    return redirect(url_for('users.index'))

@users_bp.route('/reset-password/<user_id>', methods=['POST'])
@login_required
@role_required(['Administrator'])
def reset_password(user_id):
    db = get_db()
    new_password = request.form.get('new_password', '').strip()

    if len(new_password) < 6:
        flash('New password must be at least 6 characters.', 'danger')
        return redirect(url_for('users.index'))

    try:
        db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"password_hash": generate_password_hash(new_password), "updated_at": datetime.now()}}
        )
        flash('Password successfully reset.', 'success')
    except Exception as e:
        flash(f'Error resetting password: {e}', 'danger')

    return redirect(url_for('users.index'))

@users_bp.route('/delete/<user_id>', methods=['POST'])
@login_required
@role_required(['Administrator'])
def delete(user_id):
    db = get_db()
    if str(user_id) == session.get('user_id'):
        flash('You cannot delete your own logged-in account.', 'danger')
        return redirect(url_for('users.index'))

    try:
        db.users.delete_one({"_id": ObjectId(user_id)})
        flash('User account deleted.', 'success')
    except Exception as e:
        flash(f'Error deleting user: {e}', 'danger')

    return redirect(url_for('users.index'))
