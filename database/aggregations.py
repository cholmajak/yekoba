from datetime import datetime, timedelta
from .mongo import get_db

def get_dashboard_metrics():
    """
    Execute high-performance aggregations to compute real-time farm KPIs for the dashboard.
    """
    db = get_db()
    
    # 1. Total Crops
    total_crops = db.crops.count_documents({})
    
    # 2. Total Livestock count (sum of quantity field)
    livestock_pipeline = [
        {"$match": {"status": "Active"}},
        {"$group": {"_id": None, "total": {"$sum": "$quantity"}}}
    ]
    livestock_res = list(db.livestock.aggregate(livestock_pipeline))
    total_livestock = livestock_res[0]["total"] if livestock_res else 0

    # 3. Total Active Employees
    total_employees = db.employees.count_documents({"status": "Active"})

    # 4. Total Available Inventory Items
    total_inventory = db.inventory.count_documents({})

    # 5. Low-stock inventory items (quantity_on_hand <= min_stock_level)
    low_stock_pipeline = [
        {
            "$match": {
                "$expr": {
                    "$lte": ["$quantity_on_hand", "$min_stock_level"]
                }
            }
        },
        {"$sort": {"quantity_on_hand": 1}},
        {"$limit": 5}
    ]
    low_stock_items = list(db.inventory.aggregate(low_stock_pipeline))
    low_stock_count = db.inventory.count_documents({
        "$expr": {"$lte": ["$quantity_on_hand", "$min_stock_level"]}
    })

    # 6. Total Sales / Income (UGX)
    income_pipeline = [
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}}
    ]
    income_res = list(db.sales.aggregate(income_pipeline))
    total_income = income_res[0]["total"] if income_res else 0

    # 7. Total Expenses (UGX)
    expense_pipeline = [
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
    ]
    expense_res = list(db.expenses.aggregate(expense_pipeline))
    total_expenses = expense_res[0]["total"] if expense_res else 0

    # 8. Net Profit or Loss
    net_profit = total_income - total_expenses

    # 9. Recent Farm Activities
    recent_activities = list(db.farm_activities.find().sort("activity_date", -1).limit(5))

    # 10. Upcoming / Pending Tasks
    upcoming_tasks = list(
        db.tasks.find({"status": {"$in": ["Pending", "In Progress"]}})
        .sort("due_date", 1)
        .limit(5)
    )

    return {
        "total_crops": total_crops,
        "total_livestock": total_livestock,
        "total_employees": total_employees,
        "total_inventory": total_inventory,
        "low_stock_count": low_stock_count,
        "low_stock_items": low_stock_items,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_profit": net_profit,
        "recent_activities": recent_activities,
        "upcoming_tasks": upcoming_tasks
    }

def get_income_vs_expenses_chart_data(months=6):
    """
    Returns monthly labels, income series, and expense series for Chart.js.
    Uses MongoDB aggregation pipeline with $dateToString.
    """
    db = get_db()
    today = datetime.now()
    
    # Generate past N month keys in order: ['2026-05', '2026-06', ...]
    month_keys = []
    month_labels = []
    for i in range(months - 1, -1, -1):
        d = today - timedelta(days=i * 30)
        key = d.strftime("%Y-%m")
        if key not in month_keys:
            month_keys.append(key)
            month_labels.append(d.strftime("%b %Y"))

    # Sales Aggregation by month
    sales_pipeline = [
        {
            "$group": {
                "_id": {"$substr": ["$sale_date", 0, 7]},
                "total": {"$sum": "$total_amount"}
            }
        }
    ]
    sales_data = {item["_id"]: item["total"] for item in db.sales.aggregate(sales_pipeline) if item["_id"]}

    # Expenses Aggregation by month
    expenses_pipeline = [
        {
            "$group": {
                "_id": {"$substr": ["$date", 0, 7]},
                "total": {"$sum": "$amount"}
            }
        }
    ]
    expenses_data = {item["_id"]: item["total"] for item in db.expenses.aggregate(expenses_pipeline) if item["_id"]}

    income_series = [sales_data.get(m, 0) for m in month_keys]
    expense_series = [expenses_data.get(m, 0) for m in month_keys]

    return {
        "labels": month_labels,
        "income": income_series,
        "expenses": expense_series
    }

def get_crop_production_chart_data():
    """
    Aggregates total harvested quantities grouped by crop name.
    """
    db = get_db()
    pipeline = [
        {
            "$group": {
                "_id": "$crop_name",
                "total_harvested": {"$sum": "$harvested_quantity"}
            }
        },
        {"$sort": {"total_harvested": -1}},
        {"$limit": 7}
    ]
    results = list(db.harvests.aggregate(pipeline))
    labels = [r["_id"] or "Unknown" for r in results]
    data = [r["total_harvested"] for r in results]

    return {
        "labels": labels,
        "data": data
    }

def get_livestock_breakdown():
    """
    Aggregates active livestock count by animal type.
    """
    db = get_db()
    pipeline = [
        {"$match": {"status": "Active"}},
        {
            "$group": {
                "_id": "$animal_type",
                "count": {"$sum": "$quantity"}
            }
        },
        {"$sort": {"count": -1}}
    ]
    results = list(db.livestock.aggregate(pipeline))
    labels = [r["_id"] or "Other" for r in results]
    data = [r["count"] for r in results]

    return {
        "labels": labels,
        "data": data
    }

def get_financial_report_data(start_date=None, end_date=None, category=None):
    """
    Generates detailed financial report with P&L statement and category breakdown.
    """
    db = get_db()
    
    # Expense filter match
    exp_match = {}
    if start_date and end_date:
        exp_match["date"] = {"$gte": start_date, "$lte": end_date}
    elif start_date:
        exp_match["date"] = {"$gte": start_date}
    elif end_date:
        exp_match["date"] = {"$lte": end_date}
        
    if category and category != "All":
        exp_match["category"] = category

    expenses_list = list(db.expenses.find(exp_match).sort("date", -1))
    total_expenses = sum(item.get("amount", 0) for item in expenses_list)

    # Sales filter match
    sales_match = {}
    if start_date and end_date:
        sales_match["sale_date"] = {"$gte": start_date, "$lte": end_date}
    elif start_date:
        sales_match["sale_date"] = {"$gte": start_date}
    elif end_date:
        sales_match["sale_date"] = {"$lte": end_date}

    sales_list = list(db.sales.find(sales_match).sort("sale_date", -1))
    total_sales = sum(item.get("total_amount", 0) for item in sales_list)

    # Expense by category aggregation
    category_pipeline = []
    if exp_match:
        category_pipeline.append({"$match": exp_match})
    category_pipeline.extend([
        {"$group": {"_id": "$category", "total": {"$sum": "$amount"}}},
        {"$sort": {"total": -1}}
    ])
    expense_categories = list(db.expenses.aggregate(category_pipeline))

    return {
        "total_income": total_sales,
        "total_expenses": total_expenses,
        "net_profit": total_sales - total_expenses,
        "sales": sales_list,
        "expenses": expenses_list,
        "expense_categories": expense_categories
    }
