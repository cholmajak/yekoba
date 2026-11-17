from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
from database import get_db
from modules.auth import login_required, role_required

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
@role_required(['Administrator'])
def index():
    db = get_db()
    settings = db.settings.find_one({"type": "farm_profile"})
    if not settings:
        settings = {
            "farm_name": "GreenHarvest Farm Management System",
            "owner_name": "Mukasa John Baptist",
            "location": "Mukono District, Central Uganda",
            "primary_phone": "+256 772 123 456",
            "email": "contact@greenharvest.ug",
            "currency_code": "UGX",
            "currency_symbol": "USh",
            "timezone": "Africa/Kampala (EAT)",
            "total_land_acres": 150.0
        }
        db.settings.insert_one({"type": "farm_profile", **settings})

    if request.method == 'POST':
        farm_name = request.form.get('farm_name', '').strip()
        owner_name = request.form.get('owner_name', '').strip()
        location = request.form.get('location', '').strip()
        primary_phone = request.form.get('primary_phone', '').strip()
        email = request.form.get('email', '').strip()
        total_land_acres = float(request.form.get('total_land_acres', 0))

        db.settings.update_one(
            {"type": "farm_profile"},
            {"$set": {
                "farm_name": farm_name,
                "owner_name": owner_name,
                "location": location,
                "primary_phone": primary_phone,
                "email": email,
                "total_land_acres": total_land_acres,
                "updated_at": datetime.now()
            }},
            upsert=True
        )

        flash('Farm system settings updated successfully.', 'success')
        return redirect(url_for('settings.index'))

    # Collection statistics for the database management overview
    collection_stats = {
        "Users": db.users.count_documents({}),
        "Crops": db.crops.count_documents({}),
        "Livestock": db.livestock.count_documents({}),
        "Employees": db.employees.count_documents({}),
        "Inventory Items": db.inventory.count_documents({}),
        "Stock Movements": db.stock_movements.count_documents({}),
        "Harvest Records": db.harvests.count_documents({}),
        "Sales Transactions": db.sales.count_documents({}),
        "Expense Entries": db.expenses.count_documents({}),
        "Farm Tasks": db.tasks.count_documents({}),
        "Field Activities": db.farm_activities.count_documents({}),
        "Suppliers": db.suppliers.count_documents({})
    }

    return render_template('settings/index.html', settings=settings, stats=collection_stats)
