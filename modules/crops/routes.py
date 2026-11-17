from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from bson import ObjectId
from datetime import datetime
from database import get_db
from modules.auth import login_required, role_required

crops_bp = Blueprint('crops', __name__, url_prefix='/crops')

@crops_bp.route('/')
@login_required
def index():
    db = get_db()
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', '').strip()
    field_filter = request.args.get('field', '').strip()

    query = {}
    if search:
        query["$or"] = [
            {"crop_name": {"$regex": search, "$options": "i"}},
            {"variety": {"$regex": search, "$options": "i"}},
            {"crop_id": {"$regex": search, "$options": "i"}},
            {"field_plot": {"$regex": search, "$options": "i"}}
        ]
    if status_filter and status_filter != 'All':
        query["growth_status"] = status_filter
    if field_filter and field_filter != 'All':
        query["field_plot"] = field_filter

    crops = list(db.crops.find(query).sort("planting_date", -1))
    
    # Get distinct fields for filter dropdown
    fields = db.crops.distinct("field_plot")
    
    # Statistics
    total_crops = len(crops)
    ready_for_harvest = sum(1 for c in crops if c.get("growth_status") == "Ready for Harvest")
    in_growth = sum(1 for c in crops if c.get("growth_status") in ["Planted", "Vegetative", "Flowering", "Fruiting", "Maturing"])

    return render_template(
        'crops/index.html',
        crops=crops,
        search=search,
        status_filter=status_filter,
        field_filter=field_filter,
        fields=fields,
        total_crops=total_crops,
        ready_for_harvest=ready_for_harvest,
        in_growth=in_growth
    )

@crops_bp.route('/add', methods=['GET', 'POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def add():
    db = get_db()
    if request.method == 'POST':
        crop_name = request.form.get('crop_name', '').strip()
        variety = request.form.get('variety', '').strip()
        field_plot = request.form.get('field_plot', '').strip()
        planting_date = request.form.get('planting_date', '')
        expected_harvest_date = request.form.get('expected_harvest_date', '')
        quantity_planted = float(request.form.get('quantity_planted', 0))
        quantity_planted_unit = request.form.get('quantity_planted_unit', 'kg')
        field_size = float(request.form.get('field_size', 0))
        field_size_unit = request.form.get('field_size_unit', 'Acres')
        fertilizer_used = request.form.get('fertilizer_used', '').strip()
        growth_status = request.form.get('growth_status', 'Planted')
        notes = request.form.get('notes', '').strip()

        if not crop_name or not variety or not field_plot or not planting_date:
            flash('Please fill in all required fields (Crop Name, Variety, Field, Planting Date).', 'danger')
            return render_template('crops/add.html', form=request.form)

        # Generate unique readable crop_id
        count = db.crops.count_documents({}) + 1
        crop_id = f"CRP-{datetime.now().year}-{count:03d}"

        new_crop = {
            "crop_id": crop_id,
            "crop_name": crop_name,
            "variety": variety,
            "field_plot": field_plot,
            "planting_date": planting_date,
            "expected_harvest_date": expected_harvest_date,
            "actual_harvest_date": None,
            "quantity_planted": quantity_planted,
            "quantity_planted_unit": quantity_planted_unit,
            "field_size": field_size,
            "field_size_unit": field_size_unit,
            "fertilizer_used": fertilizer_used,
            "growth_status": growth_status,
            "notes": notes,
            "created_by": session.get('username'),
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        res = db.crops.insert_one(new_crop)

        # Log initial farm activity
        db.farm_activities.insert_one({
            "crop_id": res.inserted_id,
            "crop_readable_id": crop_id,
            "crop_name": f"{crop_name} ({variety})",
            "field_plot": field_plot,
            "activity_type": "Planting",
            "activity_date": planting_date,
            "description": f"Planted {quantity_planted} {quantity_planted_unit} across {field_size} {field_size_unit}.",
            "performed_by": session.get('full_name', session.get('username')),
            "created_at": datetime.now()
        })

        flash(f'Crop record "{crop_name} ({crop_id})" registered successfully!', 'success')
        return redirect(url_for('crops.index'))

    return render_template('crops/add.html')

@crops_bp.route('/edit/<crop_id>', methods=['GET', 'POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def edit(crop_id):
    db = get_db()
    try:
        obj_id = ObjectId(crop_id)
        crop = db.crops.find_one({"_id": obj_id})
    except Exception:
        crop = db.crops.find_one({"crop_id": crop_id})

    if not crop:
        flash('Crop record not found.', 'danger')
        return redirect(url_for('crops.index'))

    if request.method == 'POST':
        crop_name = request.form.get('crop_name', '').strip()
        variety = request.form.get('variety', '').strip()
        field_plot = request.form.get('field_plot', '').strip()
        planting_date = request.form.get('planting_date', '')
        expected_harvest_date = request.form.get('expected_harvest_date', '')
        actual_harvest_date = request.form.get('actual_harvest_date', '') or None
        quantity_planted = float(request.form.get('quantity_planted', 0))
        quantity_planted_unit = request.form.get('quantity_planted_unit', 'kg')
        field_size = float(request.form.get('field_size', 0))
        field_size_unit = request.form.get('field_size_unit', 'Acres')
        fertilizer_used = request.form.get('fertilizer_used', '').strip()
        growth_status = request.form.get('growth_status', 'Planted')
        notes = request.form.get('notes', '').strip()

        db.crops.update_one(
            {"_id": crop["_id"]},
            {"$set": {
                "crop_name": crop_name,
                "variety": variety,
                "field_plot": field_plot,
                "planting_date": planting_date,
                "expected_harvest_date": expected_harvest_date,
                "actual_harvest_date": actual_harvest_date,
                "quantity_planted": quantity_planted,
                "quantity_planted_unit": quantity_planted_unit,
                "field_size": field_size,
                "field_size_unit": field_size_unit,
                "fertilizer_used": fertilizer_used,
                "growth_status": growth_status,
                "notes": notes,
                "updated_at": datetime.now()
            }}
        )

        flash(f'Crop "{crop_name}" updated successfully.', 'success')
        return redirect(url_for('crops.view', crop_id=str(crop["_id"])))

    return render_template('crops/edit.html', crop=crop)

@crops_bp.route('/view/<crop_id>')
@login_required
def view(crop_id):
    db = get_db()
    try:
        obj_id = ObjectId(crop_id)
        crop = db.crops.find_one({"_id": obj_id})
    except Exception:
        crop = db.crops.find_one({"crop_id": crop_id})

    if not crop:
        flash('Crop not found.', 'danger')
        return redirect(url_for('crops.index'))

    # Fetch associated farm activities
    activities = list(db.farm_activities.find({"crop_id": crop["_id"]}).sort("activity_date", -1))
    harvests = list(db.harvests.find({"crop_id": crop["_id"]}).sort("harvest_date", -1))

    return render_template('crops/view.html', crop=crop, activities=activities, harvests=harvests)

@crops_bp.route('/<crop_id>/activity', methods=['POST'])
@login_required
def add_activity(crop_id):
    db = get_db()
    try:
        obj_id = ObjectId(crop_id)
        crop = db.crops.find_one({"_id": obj_id})
    except Exception:
        crop = db.crops.find_one({"crop_id": crop_id})

    if not crop:
        flash('Crop not found.', 'danger')
        return redirect(url_for('crops.index'))

    activity_type = request.form.get('activity_type', 'General')
    activity_date = request.form.get('activity_date', datetime.now().strftime('%Y-%m-%d'))
    description = request.form.get('description', '').strip()

    if not description:
        flash('Activity description cannot be empty.', 'danger')
        return redirect(url_for('crops.view', crop_id=str(crop["_id"])))

    db.farm_activities.insert_one({
        "crop_id": crop["_id"],
        "crop_readable_id": crop.get("crop_id"),
        "crop_name": f"{crop.get('crop_name')} ({crop.get('variety')})",
        "field_plot": crop.get("field_plot"),
        "activity_type": activity_type,
        "activity_date": activity_date,
        "description": description,
        "performed_by": session.get('full_name', session.get('username')),
        "created_at": datetime.now()
    })

    flash(f'{activity_type} activity logged successfully.', 'success')
    return redirect(url_for('crops.view', crop_id=str(crop["_id"])))

@crops_bp.route('/delete/<crop_id>', methods=['POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def delete(crop_id):
    db = get_db()
    try:
        obj_id = ObjectId(crop_id)
        res = db.crops.delete_one({"_id": obj_id})
        # Clean up related activities
        db.farm_activities.delete_many({"crop_id": obj_id})
    except Exception:
        res = db.crops.delete_one({"crop_id": crop_id})

    if res.deleted_count > 0:
        flash('Crop record and associated activities deleted successfully.', 'success')
    else:
        flash('Failed to delete crop record.', 'danger')
    return redirect(url_for('crops.index'))
