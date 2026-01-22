from app.database import (
    inventory_collection,
    customers_collection,
    orders_collection,
)

async def create_indexes():
    await inventory_collection.create_index("item_name", unique=True)
    await customers_collection.create_index("mobile", unique=True)
    await orders_collection.create_index("created_at")
