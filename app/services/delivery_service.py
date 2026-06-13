"""
delivery_service.py
Returns today's delivery list using IST calendar day boundaries.

Order status lifecycle: CREATED → CLOSED (when fully paid)
Orders on the delivery screen are those created today that have not
been cancelled. We show ALL today's orders regardless of payment status
so the delivery person can see what to deliver.
"""
from app.database import orders_collection, customers_collection, bills_collection
from app.utils.ist_time import today_ist_utc_range, today_ist_date_str


async def get_today_delivery_list():
    start, end = today_ist_utc_range()

    # Match all orders created today (any status — deliver regardless of payment)
    pipeline = [
        {
            "$match": {
                "created_at": {"$gte": start, "$lt": end}
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
        },
        {
            "$match": {
                "customer.0": {"$exists": True},
                "bill.0":     {"$exists": True}
            }
        }
    ]

    result = []
    async for order in orders_collection.aggregate(pipeline):
        customer = order["customer"][0]
        bill     = order["bill"][0]

        result.append({
            "order_id":    str(order["_id"]),
            "customer_id": str(customer["_id"]),
            # Use "name" field — the DB has name, not shop_name
            "shop_name":   customer.get("name", customer.get("shop_name", "Unknown")),
            "area":        customer.get("area", ""),
            "mobile":      customer.get("mobile", ""),
            "bill_amount": float(bill.get("bill_amount", 0)),
            "remaining_due": float(bill.get("new_due", 0)),
            "current_due": float(customer.get("current_due", 0)),
            "order_status":order.get("status", "CREATED"),
        })

    return {
        "date":  today_ist_date_str(),
        "items": result,
    }
