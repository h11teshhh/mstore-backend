from datetime import datetime, timedelta
from bson import ObjectId
from app.database import (
    orders_collection,
    customers_collection,
    bills_collection,
)


async def get_today_delivery_list():
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    pipeline = [
        {
            "$match": {
                "created_at": {"$gte": start, "$lt": end},
                "status": {"$in": ["BILLED", "DELIVERED"]}
            }
        },
        {
            "$lookup": {
                "from": "customers",
                "localField": "customer_id",
                "foreignField": "_id",
                "as": "customer"
            }
        },
        {
            "$lookup": {
                "from": "bills",
                "localField": "_id",
                "foreignField": "order_id",
                "as": "bill"
            }
        }
    ]

    result = []
    async for order in orders_collection.aggregate(pipeline):
        customer = order["customer"][0]
        bill = order["bill"][0]

        result.append({
            "order_id": str(order["_id"]),
            "customer_id": str(customer["_id"]),
            "shop_name": customer["shop_name"],
            "area": customer.get("area", ""),
            "bill_amount": bill["bill_amount"],
            "current_due": customer["current_due"],
            "order_status": order["status"]
        })

    return result
