from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from config import Config
import logging

logger = logging.getLogger(__name__)

_mongo_client = None
_db = None

def get_client():
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(
            Config.MONGO_URI,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=10000,
            maxPoolSize=50
        )
    return _mongo_client

def get_db():
    global _db
    if _db is None:
        client = get_client()
        _db = client[Config.DB_NAME]
    return _db

def close_db():
    global _mongo_client, _db
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
        _db = None

def init_indexes():
    """
    Ensure all primary, compound, and unique indexes exist on MongoDB collections.
    """
    db = get_db()
    try:
        # Users indexes
        db.users.create_index([("email", ASCENDING)], unique=True)
        db.users.create_index([("username", ASCENDING)], unique=True)
        db.users.create_index([("role", ASCENDING)])

        # Crops indexes
        db.crops.create_index([("crop_id", ASCENDING)], unique=True)
        db.crops.create_index([("crop_name", ASCENDING), ("variety", ASCENDING)])
        db.crops.create_index([("growth_status", ASCENDING)])
        db.crops.create_index([("field_plot", ASCENDING)])
        db.crops.create_index([("planting_date", DESCENDING)])

        # Livestock indexes
        db.livestock.create_index([("tag_number", ASCENDING)], sparse=True)
        db.livestock.create_index([("animal_type", ASCENDING)])
        db.livestock.create_index([("health_status", ASCENDING)])
        db.livestock.create_index([("status", ASCENDING)])

        # Employees indexes
        db.employees.create_index([("employee_code", ASCENDING)], unique=True)
        db.employees.create_index([("status", ASCENDING)])
        db.employees.create_index([("department", ASCENDING)])

        # Inventory indexes
        db.inventory.create_index([("sku", ASCENDING)], unique=True)
        db.inventory.create_index([("category", ASCENDING)])
        db.inventory.create_index([("quantity_on_hand", ASCENDING)])

        # Stock Movements indexes
        db.stock_movements.create_index([("item_id", ASCENDING), ("timestamp", DESCENDING)])
        db.stock_movements.create_index([("movement_type", ASCENDING)])

        # Harvests indexes
        db.harvests.create_index([("crop_id", ASCENDING)])
        db.harvests.create_index([("harvest_date", DESCENDING)])
        db.harvests.create_index([("available_for_sale", ASCENDING)])

        # Sales indexes
        db.sales.create_index([("sale_date", DESCENDING)])
        db.sales.create_index([("payment_status", ASCENDING)])
        db.sales.create_index([("customer_name", ASCENDING)])

        # Expenses indexes
        db.expenses.create_index([("date", DESCENDING)])
        db.expenses.create_index([("category", ASCENDING)])

        # Tasks indexes
        db.tasks.create_index([("assigned_to", ASCENDING), ("status", ASCENDING)])
        db.tasks.create_index([("due_date", ASCENDING)])
        db.tasks.create_index([("priority", ASCENDING)])

        # Farm Activities indexes
        db.farm_activities.create_index([("crop_id", ASCENDING), ("activity_date", DESCENDING)])
        db.farm_activities.create_index([("activity_type", ASCENDING)])

        # Suppliers indexes
        db.suppliers.create_index([("name", ASCENDING)])

        logger.info("MongoDB indexes successfully verified.")
        return True
    except Exception as e:
        logger.error(f"Error creating MongoDB indexes: {e}")
        return False
