from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from bson import ObjectId
from datetime import datetime
from database import get_db
from modules.auth import login_required, role_required

livestock_bp = Blueprint('livestock', __name__, url_prefix='/livestock')

@livestock_bp.route('/')
@login_required
def index():
    db = get_db()
    search = request.args.get('search', '').strip()
    type_filter = request.args.get('type', '').strip()
    health_filter = request.args.get('health', '').strip()

    query = {"status": "Active"}
    if search:
        query["$or"] = [
            {"tag_number": {"$regex": search, "$options": "i"}},
            {"breed": {"$regex": search, "$options": "i"}},
            {"animal_type": {"$regex": search, "$options": "i"}},
            {"pen_location": {"$regex": search, "$options": "i"}}
        ]
    if type_filter and type_filter != 'All':
        query["animal_type"] = type_filter
    if health_filter and health_filter != 'All':
        query["health_status"] = health_filter

    animals = list(db.livestock.find(query).sort("created_at", -1))
    
    # Types list for filtering
    animal_types = db.livestock.distinct("animal_type")

    # Metrics
    total_heads = sum(a.get("quantity", 1) for a in animals)
    healthy_heads = sum(a.get("quantity", 1) for a in animals if a.get("health_status") == "Healthy")
    treatment_heads = sum(a.get("quantity", 1) for a in animals if a.get("health_status") in ["Under Treatment", "Sick", "Quarantined"])

    return render_template(
        'livestock/index.html',
        animals=animals,
        search=search,
        type_filter=type_filter,
        health_filter=health_filter,
        animal_types=animal_types,
        total_heads=total_heads,
        healthy_heads=healthy_heads,
        treatment_heads=treatment_heads
    )

@livestock_bp.route('/add', methods=['GET', 'POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def add():
    db = get_db()
    if request.method == 'POST':
        tracking_type = request.form.get('tracking_type', 'Individual') # Individual or Batch
        animal_type = request.form.get('animal_type', '').strip()
        breed = request.form.get('breed', '').strip()
        tag_number = request.form.get('tag_number', '').strip()
        quantity = int(request.form.get('quantity', 1)) if tracking_type == 'Batch' else 1
        gender = request.form.get('gender', 'Female')
        date_of_birth = request.form.get('date_of_birth', '')
        pen_location = request.form.get('pen_location', '').strip()
        health_status = request.form.get('health_status', 'Healthy')
        weight_kg = float(request.form.get('weight_kg', 0)) if request.form.get('weight_kg') else None
        purchase_price = float(request.form.get('purchase_price', 0)) if request.form.get('purchase_price') else 0
        notes = request.form.get('notes', '').strip()

        if not animal_type or not breed or not pen_location:
            flash('Please fill in Animal Type, Breed, and Pen/Housing Location.', 'danger')
            return render_template('livestock/add.html', form=request.form)

        if tracking_type == 'Individual' and not tag_number:
            # Auto-generate tag if omitted
            prefix = animal_type[:3].upper()
            count = db.livestock.count_documents({"animal_type": animal_type}) + 1
            tag_number = f"{prefix}-{count:04d}"

        new_animal = {
            "tracking_type": tracking_type,
            "animal_type": animal_type,
            "breed": breed,
            "tag_number": tag_number,
            "quantity": quantity,
            "gender": gender,
            "date_of_birth": date_of_birth,
            "pen_location": pen_location,
            "health_status": health_status,
            "weight_kg": weight_kg,
            "purchase_price": purchase_price,
            "status": "Active",
            "treatments": [],
            "feedings": [],
            "notes": notes,
            "created_by": session.get('username'),
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        res = db.livestock.insert_one(new_animal)

        # If purchase price was logged, automatically offer or record expense
        if purchase_price > 0:
            db.expenses.insert_one({
                "date": datetime.now().strftime("%Y-%m-%d"),
                "category": "Livestock Purchase",
                "amount": purchase_price,
                "description": f"Purchase of {quantity}x {animal_type} ({breed}, Tag/Batch: {tag_number})",
                "reference_id": str(res.inserted_id),
                "payment_method": "Cash / Mobile Money",
                "recorded_by": session.get('username'),
                "created_at": datetime.now()
            })

        flash(f'Livestock record "{tag_number} ({animal_type})" registered successfully!', 'success')
        return redirect(url_for('livestock.index'))

    return render_template('livestock/add.html')

@livestock_bp.route('/view/<animal_id>')
@login_required
def view(animal_id):
    db = get_db()
    try:
        animal = db.livestock.find_one({"_id": ObjectId(animal_id)})
    except Exception:
        animal = db.livestock.find_one({"tag_number": animal_id})

    if not animal:
        flash('Livestock record not found.', 'danger')
        return redirect(url_for('livestock.index'))

    return render_template('livestock/view.html', animal=animal)

@livestock_bp.route('/edit/<animal_id>', methods=['GET', 'POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def edit(animal_id):
    db = get_db()
    try:
        animal = db.livestock.find_one({"_id": ObjectId(animal_id)})
    except Exception:
        animal = None

    if not animal:
        flash('Livestock record not found.', 'danger')
        return redirect(url_for('livestock.index'))

    if request.method == 'POST':
        animal_type = request.form.get('animal_type', '').strip()
        breed = request.form.get('breed', '').strip()
        tag_number = request.form.get('tag_number', '').strip()
        quantity = int(request.form.get('quantity', 1))
        gender = request.form.get('gender', 'Female')
        date_of_birth = request.form.get('date_of_birth', '')
        pen_location = request.form.get('pen_location', '').strip()
        health_status = request.form.get('health_status', 'Healthy')
        status = request.form.get('status', 'Active')
        weight_kg = float(request.form.get('weight_kg', 0)) if request.form.get('weight_kg') else None
        notes = request.form.get('notes', '').strip()

        db.livestock.update_one(
            {"_id": animal["_id"]},
            {"$set": {
                "animal_type": animal_type,
                "breed": breed,
                "tag_number": tag_number,
                "quantity": quantity,
                "gender": gender,
                "date_of_birth": date_of_birth,
                "pen_location": pen_location,
                "health_status": health_status,
                "status": status,
                "weight_kg": weight_kg,
                "notes": notes,
                "updated_at": datetime.now()
            }}
        )

        flash(f'Livestock "{tag_number}" updated successfully.', 'success')
        return redirect(url_for('livestock.view', animal_id=str(animal["_id"])))

    return render_template('livestock/edit.html', animal=animal)

@livestock_bp.route('/<animal_id>/treatment', methods=['POST'])
@login_required
def add_treatment(animal_id):
    db = get_db()
    try:
        animal = db.livestock.find_one({"_id": ObjectId(animal_id)})
    except Exception:
        animal = None

    if not animal:
        flash('Animal not found.', 'danger')
        return redirect(url_for('livestock.index'))

    treatment_type = request.form.get('treatment_type', 'Vaccination')
    treatment_date = request.form.get('treatment_date', datetime.now().strftime('%Y-%m-%d'))
    medication = request.form.get('medication', '').strip()
    dosage = request.form.get('dosage', '').strip()
    administered_by = request.form.get('administered_by', session.get('full_name', 'Vet'))
    notes = request.form.get('notes', '').strip()
    update_health = request.form.get('health_status', animal.get('health_status'))

    treatment_record = {
        "treatment_type": treatment_type,
        "date": treatment_date,
        "medication": medication,
        "dosage": dosage,
        "administered_by": administered_by,
        "notes": notes,
        "created_at": datetime.now()
    }

    db.livestock.update_one(
        {"_id": animal["_id"]},
        {
            "$push": {"treatments": treatment_record},
            "$set": {"health_status": update_health, "updated_at": datetime.now()}
        }
    )

    flash('Medical treatment/vaccination recorded.', 'success')
    return redirect(url_for('livestock.view', animal_id=str(animal["_id"])))

@livestock_bp.route('/delete/<animal_id>', methods=['POST'])
@login_required
@role_required(['Administrator', 'Farm Manager'])
def delete(animal_id):
    db = get_db()
    try:
        db.livestock.delete_one({"_id": ObjectId(animal_id)})
        flash('Livestock record removed.', 'success')
    except Exception as e:
        flash(f'Error deleting record: {e}', 'danger')
    return redirect(url_for('livestock.index'))
