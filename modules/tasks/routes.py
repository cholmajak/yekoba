from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from bson import ObjectId
from datetime import datetime
from database import get_db
from modules.auth import login_required, role_required

tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks')

TASK_CATEGORIES = [
    'Planting & Sowing',
    'Weeding & Mulching',
    'Irrigation & Watering',
    'Fertilizer Application',
    'Pest & Disease Spraying',
    'Livestock Feeding & Pasture',
    'Veterinary Care & Vaccination',
    'Harvesting & Grading',
    'Equipment Maintenance',
    'General Farm Maintenance'
]

@tasks_bp.route('/')
@login_required
def index():
    db = get_db()
    status_filter = request.args.get('status', '').strip()
    priority_filter = request.args.get('priority', '').strip()
    my_tasks_only = request.args.get('my_tasks', '') == 'true'

    user_role = session.get('role', 'Farm Worker')
    user_name = session.get('full_name', session.get('username'))

    query = {}
    if user_role == 'Farm Worker' or my_tasks_only:
        # If user is a farm worker, show tasks assigned to them or unassigned
        query["$or"] = [
            {"assigned_to": user_name},
            {"assigned_to": session.get('username')},
            {"assigned_to": "Unassigned"}
        ]
    if status_filter and status_filter != 'All':
        query["status"] = status_filter
    if priority_filter and priority_filter != 'All':
        query["priority"] = priority_filter

    tasks = list(db.tasks.find(query).sort([("status", -1), ("due_date", 1)]))
    
    # Calculate overdue tasks
    today_str = datetime.now().strftime("%Y-%m-%d")
    for t in tasks:
        t["is_overdue"] = (t.get("due_date", "") < today_str and t.get("status") in ["Pending", "In Progress"])

    pending_count = sum(1 for t in tasks if t.get("status") == "Pending")
    in_progress_count = sum(1 for t in tasks if t.get("status") == "In Progress")
    completed_count = sum(1 for t in tasks if t.get("status") == "Completed")

    return render_template(
        'tasks/index.html',
        tasks=tasks,
        status_filter=status_filter,
        priority_filter=priority_filter,
        my_tasks_only=my_tasks_only,
        pending_count=pending_count,
        in_progress_count=in_progress_count,
        completed_count=completed_count,
        categories=TASK_CATEGORIES
    )

@tasks_bp.route('/add', methods=['GET', 'POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def add():
    db = get_db()
    employees = list(db.employees.find({"status": "Active"}).sort("full_name", 1))
    crops = list(db.crops.find().sort("crop_name", 1))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category = request.form.get('category', 'General Farm Maintenance')
        priority = request.form.get('priority', 'Medium')
        due_date = request.form.get('due_date', datetime.now().strftime('%Y-%m-%d'))
        assigned_to = request.form.get('assigned_to', 'Unassigned').strip()
        location_field = request.form.get('location_field', '').strip()
        description = request.form.get('description', '').strip()

        if not title:
            flash('Task title is required.', 'danger')
            return render_template('tasks/add.html', employees=employees, crops=crops, categories=TASK_CATEGORIES, form=request.form)

        new_task = {
            "title": title,
            "category": category,
            "priority": priority,
            "status": "Pending",
            "due_date": due_date,
            "assigned_to": assigned_to,
            "location_field": location_field,
            "description": description,
            "notes": "",
            "created_by": session.get('username'),
            "created_at": datetime.now(),
            "completed_at": None
        }
        db.tasks.insert_one(new_task)

        flash(f'Task "{title}" created and assigned to {assigned_to}.', 'success')
        return redirect(url_for('tasks.index'))

    return render_template('tasks/add.html', employees=employees, crops=crops, categories=TASK_CATEGORIES)

@tasks_bp.route('/update-status/<task_id>', methods=['POST'])
@login_required
def update_status(task_id):
    db = get_db()
    new_status = request.form.get('status', 'Completed')
    notes = request.form.get('notes', '').strip()

    update_fields = {
        "status": new_status,
        "updated_at": datetime.now()
    }
    if new_status == 'Completed':
        update_fields["completed_at"] = datetime.now()
    if notes:
        update_fields["notes"] = notes

    try:
        db.tasks.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": update_fields}
        )
        flash(f'Task marked as "{new_status}".', 'success')
    except Exception as e:
        flash(f'Error updating task: {e}', 'danger')

    return redirect(url_for('tasks.index'))

@tasks_bp.route('/delete/<task_id>', methods=['POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def delete(task_id):
    db = get_db()
    try:
        db.tasks.delete_one({"_id": ObjectId(task_id)})
        flash('Task removed.', 'success')
    except Exception as e:
        flash(f'Error deleting task: {e}', 'danger')
    return redirect(url_for('tasks.index'))
