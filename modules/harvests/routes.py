from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from bson import ObjectId
from datetime import datetime
from database import get_db
from modules.auth import login_required, role_required

harvests_bp = Blueprint('harvests', __name__, url_prefix='/harvests')

@harvests_bp.route('/')
@login_required
def index():
    db = get_db()
    search = request.args.get('search', '').strip()
    query = {}
    if search:
        query["$or"] = [
            {"crop_name": {"$regex": search, "$options": "i"}},
            {"field_plot": {"$regex": search, "$options": "i"}},
            {"batch_number": {"$regex": search, "$options": "i"}}
        ]

    harvests = list(db.harvests.find(query).sort("harvest_date", -1))
    
    total_yield = sum(h.get("harvested_quantity", 0) for h in harvests)
    available_stock = sum(h.get("available_for_sale", 0) for h in harvests)

    return render_template('harvests/index.html', harvests=harvests, search=search, total_yield=total_yield, available_stock=available_stock)

@harvests_bp.route('/add', methods=['GET', 'POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def add():
    db = get_db()
    crops = list(db.crops.find().sort("crop_name", 1))

    if request.method == 'POST':
        crop_id_str = request.form.get('crop_id', '').strip()
        harvested_quantity = float(request.form.get('harvested_quantity', 0))
        unit = request.form.get('unit', 'kg')
        harvest_date = request.form.get('harvest_date', datetime.now().strftime('%Y-%m-%d'))
        quality_grade = request.form.get('quality_grade', 'Grade A')
        storage_location = request.form.get('storage_location', '').strip()
        notes = request.form.get('notes', '').strip()

        crop = None
        if crop_id_str:
            try:
                crop = db.crops.find_one({"_id": ObjectId(crop_id_str)})
            except Exception:
                crop = None

        if not crop or harvested_quantity <= 0:
            flash('Please select a valid crop and enter a quantity greater than zero.', 'danger')
            return render_template('harvests/add.html', crops=crops, form=request.form)

        count = db.harvests.count_documents({}) + 1
        batch_number = f"HRV-{datetime.now().year}-{count:04d}"

        new_harvest = {
            "batch_number": batch_number,
            "crop_id": crop["_id"],
            "crop_code": crop.get("crop_id"),
            "crop_name": f"{crop.get('crop_name')} ({crop.get('variety')})",
            "field_plot": crop.get("field_plot"),
            "harvest_date": harvest_date,
            "harvested_quantity": harvested_quantity,
            "unit": unit,
            "sold_quantity": 0,
            "available_for_sale": harvested_quantity,
            "quality_grade": quality_grade,
            "storage_location": storage_location,
            "notes": notes,
            "recorded_by": session.get('username'),
            "created_at": datetime.now()
        }
        res = db.harvests.insert_one(new_harvest)

        # Update Crop actual harvest date and status if not already marked
        db.crops.update_one(
            {"_id": crop["_id"]},
            {"$set": {
                "growth_status": "Harvested",
                "actual_harvest_date": harvest_date,
                "updated_at": datetime.now()
            }}
        )

        # Log Farm Activity
        db.farm_activities.insert_one({
            "crop_id": crop["_id"],
            "crop_readable_id": crop.get("crop_id"),
            "crop_name": f"{crop.get('crop_name')} ({crop.get('variety')})",
            "field_plot": crop.get("field_plot"),
            "activity_type": "Harvesting",
            "activity_date": harvest_date,
            "description": f"Harvested {harvested_quantity} {unit} ({quality_grade}). Batch: {batch_number}.",
            "performed_by": session.get('full_name', session.get('username')),
            "created_at": datetime.now()
        })

        flash(f'Harvest record "{batch_number}" registered successfully!', 'success')
        return redirect(url_for('harvests.index'))

    return render_template('harvests/add.html', crops=crops)

@harvests_bp.route('/delete/<harvest_id>', methods=['POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def delete(harvest_id):
    db = get_db()
    try:
        db.harvests.delete_one({"_id": ObjectId(harvest_id)})
        flash('Harvest record deleted.', 'success')
    except Exception as e:
        flash(f'Error deleting harvest: {e}', 'danger')
    return redirect(url_for('harvests.index'))
