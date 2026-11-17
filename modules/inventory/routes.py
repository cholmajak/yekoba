from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from bson import ObjectId
from datetime import datetime
from database import get_db
from modules.auth import login_required, role_required

inventory_bp = Blueprint('inventory', __name__, url_prefix='/inventory')

CATEGORIES = [
    'Seeds',
    'Fertilizers',
    'Animal Feeds',
    'Pesticides',
    'Veterinary Supplies',
    'Tools and Equipment',
    'Fuel and Other Supplies'
]

@inventory_bp.route('/')
@login_required
def index():
    db = get_db()
    search = request.args.get('search', '').strip()
    category_filter = request.args.get('category', '').strip()
    low_stock_only = request.args.get('low_stock', '') == 'true'

    query = {}
    if search:
        query["$or"] = [
            {"name": {"$regex": search, "$options": "i"}},
            {"sku": {"$regex": search, "$options": "i"}},
            {"supplier": {"$regex": search, "$options": "i"}}
        ]
    if category_filter and category_filter != 'All':
        query["category"] = category_filter
    if low_stock_only:
        query["$expr"] = {"$lte": ["$quantity_on_hand", "$min_stock_level"]}

    items = list(db.inventory.find(query).sort("name", 1))

    # Overall metrics
    total_items = db.inventory.count_documents({})
    low_stock_count = db.inventory.count_documents({
        "$expr": {"$lte": ["$quantity_on_hand", "$min_stock_level"]}
    })
    total_value = sum(i.get("quantity_on_hand", 0) * i.get("unit_cost_ugx", 0) for i in items)

    return render_template(
        'inventory/index.html',
        items=items,
        search=search,
        category_filter=category_filter,
        low_stock_only=low_stock_only,
        categories=CATEGORIES,
        total_items=total_items,
        low_stock_count=low_stock_count,
        total_value=total_value
    )

@inventory_bp.route('/add', methods=['GET', 'POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def add():
    db = get_db()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        sku = request.form.get('sku', '').strip().upper()
        category = request.form.get('category', 'Seeds')
        unit = request.form.get('unit', 'kg')
        quantity_on_hand = float(request.form.get('quantity_on_hand', 0))
        min_stock_level = float(request.form.get('min_stock_level', 10))
        unit_cost_ugx = float(request.form.get('unit_cost_ugx', 0))
        storage_location = request.form.get('storage_location', '').strip()
        supplier = request.form.get('supplier', '').strip()
        notes = request.form.get('notes', '').strip()

        if not name:
            flash('Item name is required.', 'danger')
            return render_template('inventory/add.html', categories=CATEGORIES, form=request.form)

        if not sku:
            cat_code = category[:3].upper()
            count = db.inventory.count_documents({"category": category}) + 1
            sku = f"INV-{cat_code}-{count:03d}"

        # Check existing SKU
        if db.inventory.find_one({"sku": sku}):
            flash(f'An item with SKU "{sku}" already exists.', 'danger')
            return render_template('inventory/add.html', categories=CATEGORIES, form=request.form)

        new_item = {
            "sku": sku,
            "name": name,
            "category": category,
            "unit": unit,
            "quantity_on_hand": quantity_on_hand,
            "min_stock_level": min_stock_level,
            "unit_cost_ugx": unit_cost_ugx,
            "storage_location": storage_location,
            "supplier": supplier,
            "notes": notes,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        res = db.inventory.insert_one(new_item)

        # Log initial stock movement
        if quantity_on_hand > 0:
            db.stock_movements.insert_one({
                "item_id": res.inserted_id,
                "sku": sku,
                "item_name": name,
                "movement_type": "INITIAL_STOCK",
                "quantity": quantity_on_hand,
                "previous_stock": 0,
                "new_stock": quantity_on_hand,
                "reason": "Initial inventory setup",
                "reference": "System Setup",
                "performed_by": session.get('username'),
                "timestamp": datetime.now()
            })

        flash(f'Item "{name}" added to inventory successfully.', 'success')
        return redirect(url_for('inventory.index'))

    return render_template('inventory/add.html', categories=CATEGORIES)

@inventory_bp.route('/adjust/<item_id>', methods=['POST'])
@login_required
@role_required(['Administrator', 'Farm Manager', 'Farm Worker'])
def adjust_stock(item_id):
    db = get_db()
    try:
        item = db.inventory.find_one({"_id": ObjectId(item_id)})
    except Exception:
        item = None

    if not item:
        flash('Inventory item not found.', 'danger')
        return redirect(url_for('inventory.index'))

    adjustment_type = request.form.get('adjustment_type') # 'ADD' or 'DEDUCT'
    qty = float(request.form.get('quantity', 0))
    reason = request.form.get('reason', '').strip()

    if qty <= 0:
        flash('Quantity must be greater than zero.', 'danger')
        return redirect(url_for('inventory.index'))

    current_qty = item.get('quantity_on_hand', 0)

    if adjustment_type == 'DEDUCT':
        if qty > current_qty:
            flash(f'Cannot deduct {qty} {item["unit"]}. Only {current_qty} {item["unit"]} available in stock.', 'danger')
            return redirect(url_for('inventory.index'))
        new_qty = current_qty - qty
        mov_type = "USAGE_OUT"
    else:
        new_qty = current_qty + qty
        mov_type = "RESTOCK_IN"

    # Update item in database
    db.inventory.update_one(
        {"_id": item["_id"]},
        {"$set": {"quantity_on_hand": new_qty, "updated_at": datetime.now()}}
    )

    # Log movement in stock_movements collection
    db.stock_movements.insert_one({
        "item_id": item["_id"],
        "sku": item["sku"],
        "item_name": item["name"],
        "movement_type": mov_type,
        "quantity": qty,
        "previous_stock": current_qty,
        "new_stock": new_qty,
        "reason": reason or ("Stock usage" if adjustment_type == 'DEDUCT' else "Restock purchase"),
        "reference": request.form.get('reference', 'Manual Adjustment'),
        "performed_by": session.get('username'),
        "timestamp": datetime.now()
    })

    # If restock with cost, can optionally record expense
    if adjustment_type == 'ADD' and request.form.get('record_expense') == 'true':
        cost = qty * item.get('unit_cost_ugx', 0)
        if cost > 0:
            db.expenses.insert_one({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "category": f"Inventory: {item.get('category')}",
                "amount": cost,
                "description": f"Restocked {qty} {item['unit']} of {item['name']}",
                "reference_id": str(item["_id"]),
                "payment_method": "Cash / Supplier Invoice",
                "recorded_by": session.get('username'),
                "created_at": datetime.now()
            })

    flash(f'Stock for "{item["name"]}" updated to {new_qty} {item["unit"]}.', 'success')
    return redirect(url_for('inventory.index'))

@inventory_bp.route('/movements')
@login_required
def movements():
    db = get_db()
    sku = request.args.get('sku', '').strip()
    query = {}
    if sku:
        query["sku"] = sku

    logs = list(db.stock_movements.find(query).sort("timestamp", -1).limit(100))
    return render_template('inventory/movements.html', logs=logs, sku=sku)

@inventory_bp.route('/edit/<item_id>', methods=['GET', 'POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def edit(item_id):
    db = get_db()
    try:
        item = db.inventory.find_one({"_id": ObjectId(item_id)})
    except Exception:
        item = None

    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('inventory.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', 'Seeds')
        unit = request.form.get('unit', 'kg')
        min_stock_level = float(request.form.get('min_stock_level', 10))
        unit_cost_ugx = float(request.form.get('unit_cost_ugx', 0))
        storage_location = request.form.get('storage_location', '').strip()
        supplier = request.form.get('supplier', '').strip()
        notes = request.form.get('notes', '').strip()

        db.inventory.update_one(
            {"_id": item["_id"]},
            {"$set": {
                "name": name,
                "category": category,
                "unit": unit,
                "min_stock_level": min_stock_level,
                "unit_cost_ugx": unit_cost_ugx,
                "storage_location": storage_location,
                "supplier": supplier,
                "notes": notes,
                "updated_at": datetime.now()
            }}
        )

        flash(f'Inventory item "{name}" updated.', 'success')
        return redirect(url_for('inventory.index'))

    return render_template('inventory/edit.html', item=item, categories=CATEGORIES)

@inventory_bp.route('/delete/<item_id>', methods=['POST'])
@login_required
@role_required(['Administrator'])
def delete(item_id):
    db = get_db()
    try:
        db.inventory.delete_one({"_id": ObjectId(item_id)})
        flash('Inventory item removed.', 'success')
    except Exception as e:
        flash(f'Error deleting item: {e}', 'danger')
    return redirect(url_for('inventory.index'))
