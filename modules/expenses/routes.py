from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from bson import ObjectId
from datetime import datetime
from database import get_db
from modules.auth import login_required, role_required

expenses_bp = Blueprint('expenses', __name__, url_prefix='/expenses')

EXPENSE_CATEGORIES = [
    'Seeds & Planting Materials',
    'Fertilizers & Soil Conditioning',
    'Animal Feeds & Supplements',
    'Pesticides & Crop Protection',
    'Veterinary Services & Medicine',
    'Fuel, Oil & Lubricants',
    'Equipment & Machinery Maintenance',
    'Employee Wages & Salaries',
    'Electricity & Water Utilities',
    'Land Lease & Property',
    'Packaging & Transport',
    'General Farm Administration'
]

@expenses_bp.route('/')
@login_required
def index():
    db = get_db()
    search = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    query = {}
    if search:
        query["$or"] = [
            {"description": {"$regex": search, "$options": "i"}},
            {"vendor_supplier": {"$regex": search, "$options": "i"}},
            {"category": {"$regex": search, "$options": "i"}}
        ]
    if category_filter and category_filter != 'All':
        query["category"] = category_filter
    if start_date and end_date:
        query["date"] = {"$gte": start_date, "$lte": end_date}
    elif start_date:
        query["date"] = {"$gte": start_date}
    elif end_date:
        query["date"] = {"$lte": end_date}

    expenses = list(db.expenses.find(query).sort("date", -1))
    total_expenses = sum(e.get("amount", 0) for e in expenses)

    return render_template(
        'expenses/index.html',
        expenses=expenses,
        categories=EXPENSE_CATEGORIES,
        search=search,
        category_filter=category_filter,
        start_date=start_date,
        end_date=end_date,
        total_expenses=total_expenses
    )

@expenses_bp.route('/add', methods=['GET', 'POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def add():
    db = get_db()
    suppliers = list(db.suppliers.find().sort("name", 1))

    if request.method == 'POST':
        date = request.form.get('date', datetime.now().strftime('%Y-%m-%d'))
        category = request.form.get('category', 'General Farm Administration')
        amount = float(request.form.get('amount', 0))
        description = request.form.get('description', '').strip()
        vendor_supplier = request.form.get('vendor_supplier', '').strip()
        payment_method = request.form.get('payment_method', 'Cash / Mobile Money')
        receipt_ref = request.form.get('receipt_ref', '').strip()
        notes = request.form.get('notes', '').strip()

        if amount <= 0 or not description:
            flash('Please enter a valid expense amount and description.', 'danger')
            return render_template('expenses/add.html', categories=EXPENSE_CATEGORIES, suppliers=suppliers, form=request.form)

        new_expense = {
            "date": date,
            "category": category,
            "amount": amount,
            "description": description,
            "vendor_supplier": vendor_supplier,
            "payment_method": payment_method,
            "receipt_ref": receipt_ref,
            "notes": notes,
            "recorded_by": session.get('username'),
            "created_at": datetime.now()
        }
        db.expenses.insert_one(new_expense)

        flash(f'Expense of UGX {amount:,.0f} ({category}) recorded successfully!', 'success')
        return redirect(url_for('expenses.index'))

    return render_template('expenses/add.html', categories=EXPENSE_CATEGORIES, suppliers=suppliers)

@expenses_bp.route('/delete/<expense_id>', methods=['POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def delete(expense_id):
    db = get_db()
    try:
        db.expenses.delete_one({"_id": ObjectId(expense_id)})
        flash('Expense record deleted.', 'success')
    except Exception as e:
        flash(f'Error deleting expense: {e}', 'danger')
    return redirect(url_for('expenses.index'))
