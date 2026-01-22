from bson import ObjectId
from app.database import bills_collection, customers_collection


async def get_bill_for_print(order_id: str):
    bill = await bills_collection.find_one({"order_id": ObjectId(order_id)})
    customer = await customers_collection.find_one({"_id": bill["customer_id"]})

    return {
        "shop_name": customer["shop_name"],
        "bill_date": bill["created_at"],
        "items": bill["items"],
        "bill_amount": bill["bill_amount"],
        "previous_due": bill["previous_due"],
        "new_due": bill["new_due"]
    }
