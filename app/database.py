from motor.motor_asyncio import AsyncIOMotorClient
from app.config import MONGO_URL, DB_NAME

client = AsyncIOMotorClient(MONGO_URL)
database = client[DB_NAME]

# Collections
inventory_collection = database["inventory"]
inventory_itemdetails_collection = database["inventory_itemdetails"]
customers_collection = database["customers"]
orders_collection = database["orders"]
# order_items_collection = database["order_items"]
payments_collection = database["payments"]
bills_collection = database["bills"]
users_collection = database["users"]

print("MongoDB Atlas connected successfully")
