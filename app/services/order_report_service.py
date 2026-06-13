"""
order_report_service.py
Returns today's orders for a specific customer using IST day boundaries.
"""
from bson import ObjectId
from app.database import bills_collection
from app.utils.ist_time import today_ist_utc_range, today_ist_date_str


async def get_today_orders_for_customer(customer_id: str):
    start, end = today_ist_utc_range()

    pipeline = [
        {
            "$match": {
                "customer_id": ObjectId(customer_id),
                "created_at":  {"$gte": start, "$lt": end}
            }
        },
        {"$unwind": "$items"},
        {
            "$lookup": {
                "from":         "inventory",
                "localField":   "items.item_id",
                "foreignField": "_id",
                "as":           "item_info"
            }
        },
        {"$unwind": {"path": "$item_info", "preserveNullAndEmptyArrays": True}},
        {
            "$group": {
                "_id":         "$order_id",
                "created_at":  {"$first": "$created_at"},
                "bill_amount": {"$first": "$bill_amount"},
                "new_due":     {"$first": "$new_due"},
                "items": {
                    "$push": {
                        "item_id":   "$items.item_id",
                        "item_name": {"$ifNull": ["$item_info.item_name", "$items.item_name"]},
                        "quantity":  "$items.quantity",
                        "price":     "$items.price",
                        "total":     "$items.total"
                    }
                }
            }
        },
        {"$sort": {"created_at": 1}}
    ]

    orders = []
    async for o in bills_collection.aggregate(pipeline):
        orders.append({
            "order_id":    str(o["_id"]),
            "created_at":  o["created_at"],
            "bill_amount": float(o.get("bill_amount", 0)),
            "remaining_due": float(o.get("new_due", 0)),
            "items": [
                {
                    "item_id":   str(i["item_id"]),
                    "item_name": i.get("item_name", "Unknown"),
                    "quantity":  i["quantity"],
                    "price":     i["price"],
                    "total":     i["total"]
                }
                for i in o["items"]
            ]
        })

    return {
        "customer_id":  customer_id,
        "date":         today_ist_date_str(),
        "total_orders": len(orders),
        "orders":       orders,
    }
