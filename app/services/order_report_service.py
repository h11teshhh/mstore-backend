from datetime import datetime, timedelta
from bson import ObjectId
from app.database import bills_collection


async def get_today_orders_for_customer(customer_id: str):
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    pipeline = [
        {
            "$match": {
                "customer_id": ObjectId(customer_id),
                "created_at": {"$gte": start, "$lt": end}
            }
        },
        {"$unwind": "$items"},
        {
            "$lookup": {
                "from": "inventory",
                "localField": "items.item_id",
                "foreignField": "_id",
                "as": "item_info"
            }
        },
        {"$unwind": "$item_info"},
        {
            "$group": {
                "_id": "$order_id",
                "created_at": {"$first": "$created_at"},
                "bill_amount": {"$first": "$bill_amount"},
                "items": {
                    "$push": {
                        "item_id": "$items.item_id",
                        "item_name": "$item_info.item_name",
                        "quantity": "$items.quantity",
                        "price": "$items.price",
                        "total": "$items.total"
                    }
                }
            }
        },
        {"$sort": {"created_at": 1}}
    ]

    orders = []
    async for o in bills_collection.aggregate(pipeline):
        orders.append({
            "order_id": str(o["_id"]),
            "created_at": o["created_at"],
            "bill_amount": o["bill_amount"],
            "items": [
                {
                    "item_id": str(i["item_id"]),   # ✅ FIX HERE
                    "item_name": i["item_name"],
                    "quantity": i["quantity"],
                    "price": i["price"],
                    "total": i["total"]
                }
                for i in o["items"]
            ]
        })

    return {
        "customer_id": customer_id,
        "date": start.date().isoformat(),
        "total_orders": len(orders),
        "orders": orders
    }
