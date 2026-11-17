from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from bson import ObjectId
from datetime import datetime
from database import get_db
from modules.auth import login_required, role_required

employees_bp = Blueprint('employees', __name__, url_prefix='/employees')

@employees_bp.route('/')
@login_required
def index():
    db = get_db()
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'Active').strip()
    dept_filter = request.args.get('department', '').strip()

    query = {}
    if status_filter and status_filter != 'All':
        query["status"] = status_filter
    if dept_filter and dept_filter != 'All':
        query["department"] = dept_filter
    if search:
        query["$or"] = [
            {"full_name": {"$regex": search, "$options": "i"}},
            {"employee_code": {"$regex": search, "$options": "i"}},
            {"job_title": {"$regex": search, "$options": "i"}},
            {"phone": {"$regex": search, "$options": "i"}}
        ]

    employees = list(db.employees.find(query).sort("full_name", 1))
    departments = db.employees.distinct("department")

    # Metrics
    total_active = db.employees.count_documents({"status": "Active"})
    total_on_leave = db.employees.count_documents({"status": "On Leave"})

    return render_template(
        'employees/index.html',
        employees=employees,
        search=search,
        status_filter=status_filter,
        dept_filter=dept_filter,
        departments=departments,
        total_active=total_active,
        total_on_leave=total_on_leave
    )

@employees_bp.route('/add', methods=['GET', 'POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def add():
    db = get_db()
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        job_title = request.form.get('job_title', '').strip()
        department = request.form.get('department', 'Field Operations').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        national_id = request.form.get('national_id', '').strip()
        hire_date = request.form.get('hire_date', datetime.now().strftime('%Y-%m-%d'))
        monthly_salary_ugx = float(request.form.get('monthly_salary_ugx', 0))
        emergency_contact = request.form.get('emergency_contact', '').strip()
        duties_assigned = request.form.get('duties_assigned', '').strip()

        if not full_name or not job_title or not phone:
            flash('Please fill in Full Name, Job Title, and Phone Number.', 'danger')
            return render_template('employees/add.html', form=request.form)

        # Unique code
        count = db.employees.count_documents({}) + 1
        employee_code = f"EMP-{count:04d}"

        new_emp = {
            "employee_code": employee_code,
            "full_name": full_name,
            "job_title": job_title,
            "department": department,
            "phone": phone,
            "email": email,
            "national_id": national_id,
            "hire_date": hire_date,
            "monthly_salary_ugx": monthly_salary_ugx,
            "emergency_contact": emergency_contact,
            "duties_assigned": duties_assigned,
            "status": "Active",
            "attendance": [],
            "salary_payments": [],
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        db.employees.insert_one(new_emp)

        flash(f'Employee "{full_name} ({employee_code})" registered successfully!', 'success')
        return redirect(url_for('employees.index'))

    return render_template('employees/add.html')

@employees_bp.route('/view/<emp_id>')
@login_required
def view(emp_id):
    db = get_db()
    try:
        emp = db.employees.find_one({"_id": ObjectId(emp_id)})
    except Exception:
        emp = db.employees.find_one({"employee_code": emp_id})

    if not emp:
        flash('Employee not found.', 'danger')
        return redirect(url_for('employees.index'))

    # Get tasks assigned to this employee
    tasks = list(db.tasks.find({"assigned_to": emp.get("full_name")}).sort("due_date", 1))

    return render_template('employees/view.html', emp=emp, tasks=tasks)

@employees_bp.route('/edit/<emp_id>', methods=['GET', 'POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def edit(emp_id):
    db = get_db()
    try:
        emp = db.employees.find_one({"_id": ObjectId(emp_id)})
    except Exception:
        emp = None

    if not emp:
        flash('Employee not found.', 'danger')
        return redirect(url_for('employees.index'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        job_title = request.form.get('job_title', '').strip()
        department = request.form.get('department', '').strip()
        phone = request.form.get('phone', '').strip()
        email = request.form.get('email', '').strip()
        status = request.form.get('status', 'Active')
        monthly_salary_ugx = float(request.form.get('monthly_salary_ugx', 0))
        duties_assigned = request.form.get('duties_assigned', '').strip()

        db.employees.update_one(
            {"_id": emp["_id"]},
            {"$set": {
                "full_name": full_name,
                "job_title": job_title,
                "department": department,
                "phone": phone,
                "email": email,
                "status": status,
                "monthly_salary_ugx": monthly_salary_ugx,
                "duties_assigned": duties_assigned,
                "updated_at": datetime.now()
            }}
        )

        flash(f'Employee "{full_name}" updated successfully.', 'success')
        return redirect(url_for('employees.view', emp_id=str(emp["_id"])))

    return render_template('employees/edit.html', emp=emp)

@employees_bp.route('/<emp_id>/attendance', methods=['POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def log_attendance(emp_id):
    db = get_db()
    try:
        emp = db.employees.find_one({"_id": ObjectId(emp_id)})
    except Exception:
        emp = None

    if not emp:
        flash('Employee not found.', 'danger')
        return redirect(url_for('employees.index'))

    att_date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
    status = request.form.get('status', 'Present') # Present, Absent, Half-Day, Sick Leave
    notes = request.form.get('notes', '').strip()

    record = {
        "date": att_date,
        "status": status,
        "notes": notes,
        "recorded_by": session.get('username'),
        "created_at": datetime.now()
    }

    db.employees.update_one(
        {"_id": emp["_id"]},
        {"$push": {"attendance": record}}
    )

    flash(f'Attendance recorded as "{status}" for {emp["full_name"]}.', 'success')
    return redirect(url_for('employees.view', emp_id=str(emp["_id"])))

@employees_bp.route('/<emp_id>/salary-payment', methods=['POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def pay_salary(emp_id):
    db = get_db()
    try:
        emp = db.employees.find_one({"_id": ObjectId(emp_id)})
    except Exception:
        emp = None

    if not emp:
        flash('Employee not found.', 'danger')
        return redirect(url_for('employees.index'))

    amount = float(request.form.get('amount', emp.get('monthly_salary_ugx', 0)))
    pay_date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
    period = request.form.get('period', datetime.now().strftime('%B %Y'))
    notes = request.form.get('notes', '').strip()

    # Record salary payment under employee
    payment_record = {
        "amount_ugx": amount,
        "date": pay_date,
        "period": period,
        "notes": notes,
        "paid_by": session.get('username'),
        "created_at": datetime.now()
    }
    db.employees.update_one(
        {"_id": emp["_id"]},
        {"$push": {"salary_payments": payment_record}}
    )

    # Also automatically record as Farm Expense
    db.expenses.insert_one({
        "date": pay_date,
        "category": "Employee Wages & Salaries",
        "amount": amount,
        "description": f"Salary payment for {emp['full_name']} ({period})",
        "reference_id": str(emp["_id"]),
        "payment_method": "Bank Transfer / Mobile Money",
        "recorded_by": session.get('username'),
        "created_at": datetime.now()
    })

    flash(f'Salary payment of UGX {amount:,.0f} recorded for {emp["full_name"]}.', 'success')
    return redirect(url_for('employees.view', emp_id=str(emp["_id"])))
