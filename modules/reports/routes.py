import csv
import io
from flask import Blueprint, render_template, request, Response, session
from datetime import datetime, timedelta
from database import get_db, get_financial_report_data
from modules.auth import login_required, role_required

reports_bp = Blueprint('reports', __name__, url_prefix='/reports')

@reports_bp.route('/')
@login_required
@role_required(['Administrator', 'Farm Manager'])
def index():
    report_type = request.args.get('type', 'financial')
    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    
    db = get_db()
    data = {}

    if report_type == 'financial':
        data = get_financial_report_data(start_date=start_date, end_date=end_date)
    elif report_type == 'crops':
        harvests = list(db.harvests.find({
            "harvest_date": {"$gte": start_date, "$lte": end_date}
        }).sort("harvest_date", -1))
        data = {
            "harvests": harvests,
            "total_harvests": len(harvests),
            "total_yield": sum(h.get("harvested_quantity", 0) for h in harvests),
            "total_sold": sum(h.get("sold_quantity", 0) for h in harvests),
            "total_available": sum(h.get("available_for_sale", 0) for h in harvests)
        }
    elif report_type == 'livestock':
        animals = list(db.livestock.find({"status": "Active"}).sort("animal_type", 1))
        data = {
            "animals": animals,
            "total_heads": sum(a.get("quantity", 1) for a in animals),
            "healthy": sum(a.get("quantity", 1) for a in animals if a.get("health_status") == "Healthy"),
            "under_treatment": sum(a.get("quantity", 1) for a in animals if a.get("health_status") in ["Under Treatment", "Sick", "Quarantined"])
        }
    elif report_type == 'inventory':
        movements = list(db.stock_movements.find({
            "timestamp": {
                "$gte": datetime.strptime(start_date, "%Y-%m-%d"),
                "$lte": datetime.strptime(end_date + " 23:59:59", "%Y-%m-%d %H:%M:%S")
            }
        }).sort("timestamp", -1))
        data = {
            "movements": movements,
            "total_movements": len(movements)
        }
    elif report_type == 'tasks':
        tasks = list(db.tasks.find({
            "due_date": {"$gte": start_date, "$lte": end_date}
        }).sort("due_date", -1))
        data = {
            "tasks": tasks,
            "total_tasks": len(tasks),
            "completed": sum(1 for t in tasks if t.get("status") == "Completed"),
            "pending": sum(1 for t in tasks if t.get("status") in ["Pending", "In Progress"])
        }

    return render_template(
        'reports/index.html',
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        data=data
    )

@reports_bp.route('/export/csv')
@login_required
@role_required(['Administrator', 'Farm Manager'])
def export_csv():
    report_type = request.args.get('type', 'financial')
    start_date = request.args.get('start_date', (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'))
    end_date = request.args.get('end_date', datetime.now().strftime('%Y-%m-%d'))
    db = get_db()

    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == 'financial':
        writer.writerow(['Type', 'Date', 'Category / Product', 'Description / Customer', 'Amount (UGX)', 'Payment Status / Method'])
        
        # Sales
        sales = db.sales.find({"sale_date": {"$gte": start_date, "$lte": end_date}}).sort("sale_date", -1)
        for s in sales:
            writer.writerow(['INCOME (Sale)', s.get('sale_date'), s.get('product_name'), s.get('customer_name'), s.get('total_amount', 0), s.get('payment_status')])

        # Expenses
        expenses = db.expenses.find({"date": {"$gte": start_date, "$lte": end_date}}).sort("date", -1)
        for e in expenses:
            writer.writerow(['EXPENSE', e.get('date'), e.get('category'), e.get('description'), -e.get('amount', 0), e.get('payment_method')])

    elif report_type == 'crops':
        writer.writerow(['Batch Number', 'Crop Name', 'Field / Plot', 'Harvest Date', 'Harvested Quantity', 'Unit', 'Sold Quantity', 'Available For Sale', 'Quality Grade'])
        harvests = db.harvests.find({"harvest_date": {"$gte": start_date, "$lte": end_date}}).sort("harvest_date", -1)
        for h in harvests:
            writer.writerow([
                h.get('batch_number'),
                h.get('crop_name'),
                h.get('field_plot'),
                h.get('harvest_date'),
                h.get('harvested_quantity'),
                h.get('unit'),
                h.get('sold_quantity', 0),
                h.get('available_for_sale', 0),
                h.get('quality_grade')
            ])

    elif report_type == 'inventory':
        writer.writerow(['Date / Time', 'SKU', 'Item Name', 'Movement Type', 'Quantity', 'Previous Stock', 'New Stock', 'Reason', 'User'])
        movements = db.stock_movements.find().sort("timestamp", -1)
        for m in movements:
            ts = m.get('timestamp')
            dt_str = ts.strftime('%Y-%m-%d %H:%M') if isinstance(ts, datetime) else str(ts)
            writer.writerow([
                dt_str,
                m.get('sku'),
                m.get('item_name'),
                m.get('movement_type'),
                m.get('quantity'),
                m.get('previous_stock'),
                m.get('new_stock'),
                m.get('reason'),
                m.get('performed_by')
            ])

    filename = f"farm_{report_type}_report_{start_date}_to_{end_date}.csv"
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )
