from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from bson import ObjectId
from datetime import datetime
from database import get_db
from modules.auth import login_required, role_required

sales_bp = Blueprint('sales', __name__, url_prefix='/sales')

@sales_bp.route('/')
@login_required
def index():
    db = get_db()
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()

    query = {}
    if search:
        query["$or"] = [
            {"invoice_number": {"$regex": search, "$options": "i"}},
            {"customer_name": {"$regex": search, "$options": "i"}},
            {"product_name": {"$regex": search, "$options": "i"}}
        ]
    if status_filter and status_filter != 'All':
        query["payment_status"] = status_filter

    sales = list(db.sales.find(query).sort("sale_date", -1))

    total_revenue = sum(s.get("total_amount", 0) for s in sales)
    paid_revenue = sum(s.get("total_amount", 0) for s in sales if s.get("payment_status") == "Paid")
    pending_revenue = sum(s.get("total_amount", 0) for s in sales if s.get("payment_status") in ["Pending", "Partial"])

    return render_template(
        'sales/index.html',
        sales=sales,
        search=search,
        status_filter=status_filter,
        total_revenue=total_revenue,
        paid_revenue=paid_revenue,
        pending_revenue=pending_revenue
    )

@sales_bp.route('/add', methods=['GET', 'POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def add():
    db = get_db()
    # Fetch available harvests with available stock > 0
    available_harvests = list(db.harvests.find({"available_for_sale": {"$gt": 0}}).sort("harvest_date", -1))
    # Fetch active livestock that could be sold
    livestock_list = list(db.livestock.find({"status": "Active"}).sort("tag_number", 1))

    if request.method == 'POST':
        item_source = request.form.get('item_source', 'harvest') # 'harvest', 'livestock', 'other'
        customer_name = request.form.get('customer_name', '').strip()
        customer_phone = request.form.get('customer_phone', '').strip()
        sale_date = request.form.get('sale_date', datetime.now().strftime('%Y-%m-%d'))
        payment_status = request.form.get('payment_status', 'Paid') # Paid, Pending, Partial
        payment_method = request.form.get('payment_method', 'Cash / Mobile Money')
        notes = request.form.get('notes', '').strip()

        harvest_id_str = request.form.get('harvest_id', '')
        livestock_id_str = request.form.get('livestock_id', '')

        if not customer_name:
            flash('Customer name is required.', 'danger')
            return render_template('sales/add.html', available_harvests=available_harvests, livestock_list=livestock_list, form=request.form)

        product_name = ""
        quantity = 0.0
        unit = "units"
        unit_price = 0.0
        total_amount = 0.0
        harvest_obj_id = None
        livestock_obj_id = None

        if item_source == 'harvest':
            if not harvest_id_str:
                flash('Please select a harvest lot.', 'danger')
                return render_template('sales/add.html', available_harvests=available_harvests, livestock_list=livestock_list, form=request.form)
            harvest = db.harvests.find_one({"_id": ObjectId(harvest_id_str)})
            if not harvest:
                flash('Selected harvest lot not found.', 'danger')
                return render_template('sales/add.html', available_harvests=available_harvests, livestock_list=livestock_list, form=request.form)

            product_name = harvest.get("crop_name")
            unit = harvest.get("unit", "kg")
            quantity = float(request.form.get('quantity', 0))
            unit_price = float(request.form.get('unit_price', 0))

            if quantity <= 0:
                flash('Quantity must be greater than zero.', 'danger')
                return render_template('sales/add.html', available_harvests=available_harvests, livestock_list=livestock_list, form=request.form)

            avail = harvest.get("available_for_sale", 0)
            if quantity > avail:
                flash(f'Cannot sell {quantity} {unit}. Only {avail} {unit} available in this harvest lot.', 'danger')
                return render_template('sales/add.html', available_harvests=available_harvests, livestock_list=livestock_list, form=request.form)

            harvest_obj_id = harvest["_id"]

            # Deduct harvest available_for_sale and increase sold_quantity
            db.harvests.update_one(
                {"_id": harvest["_id"]},
                {
                    "$inc": {"available_for_sale": -quantity, "sold_quantity": quantity},
                    "$set": {"updated_at": datetime.now()}
                }
            )

        elif item_source == 'livestock':
            if not livestock_id_str:
                flash('Please select an animal or batch.', 'danger')
                return render_template('sales/add.html', available_harvests=available_harvests, livestock_list=livestock_list, form=request.form)
            animal = db.livestock.find_one({"_id": ObjectId(livestock_id_str)})
            if not animal:
                flash('Animal record not found.', 'danger')
                return render_template('sales/add.html', available_harvests=available_harvests, livestock_list=livestock_list, form=request.form)

            product_name = f"{animal.get('animal_type')} ({animal.get('breed')}, Tag: {animal.get('tag_number')})"
            quantity = float(request.form.get('quantity', 1))
            unit = "heads"
            unit_price = float(request.form.get('unit_price', 0))
            livestock_obj_id = animal["_id"]

            # Update animal status to Sold
            db.livestock.update_one(
                {"_id": animal["_id"]},
                {"$set": {"status": "Sold", "sold_at": datetime.now()}}
            )

        else: # Other custom produce or processed items (e.g. Milk, Eggs, Honey)
            product_name = request.form.get('custom_product_name', 'Farm Produce').strip()
            quantity = float(request.form.get('quantity', 1))
            unit = request.form.get('custom_unit', 'units').strip()
            unit_price = float(request.form.get('unit_price', 0))

        total_amount = quantity * unit_price
        count = db.sales.count_documents({}) + 1
        invoice_number = f"INV-{datetime.now().year}-{count:04d}"

        new_sale = {
            "invoice_number": invoice_number,
            "sale_date": sale_date,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "product_name": product_name,
            "item_source": item_source,
            "harvest_id": harvest_obj_id,
            "livestock_id": livestock_obj_id,
            "quantity": quantity,
            "unit": unit,
            "unit_price": unit_price,
            "total_amount": total_amount,
            "payment_status": payment_status,
            "payment_method": payment_method,
            "notes": notes,
            "recorded_by": session.get('username'),
            "created_at": datetime.now()
        }
        db.sales.insert_one(new_sale)

        flash(f'Sale recorded successfully! Invoice {invoice_number} for UGX {total_amount:,.0f}', 'success')
        return redirect(url_for('sales.index'))

    return render_template('sales/add.html', available_harvests=available_harvests, livestock_list=livestock_list)

@sales_bp.route('/view/<sale_id>')
@login_required
def view(sale_id):
    db = get_db()
    try:
        sale = db.sales.find_one({"_id": ObjectId(sale_id)})
    except Exception:
        sale = db.sales.find_one({"invoice_number": sale_id})

    if not sale:
        flash('Sale record not found.', 'danger')
        return redirect(url_for('sales.index'))

    return render_template('sales/view.html', sale=sale)

@sales_bp.route('/update-status/<sale_id>', methods=['POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def update_status(sale_id):
    db = get_db()
    new_status = request.form.get('payment_status', 'Paid')
    try:
        db.sales.update_one(
            {"_id": ObjectId(sale_id)},
            {"$set": {"payment_status": new_status, "updated_at": datetime.now()}}
        )
        flash('Payment status updated.', 'success')
    except Exception as e:
        flash(f'Error updating status: {e}', 'danger')
    return redirect(url_for('sales.index'))
