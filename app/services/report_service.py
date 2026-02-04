# app/services/report_service.py

from datetime import datetime, timedelta
from bson import ObjectId
from app.database import (
    customers_collection,
    orders_collection,
    bills_collection,
    inventory_collection
)


async def get_today_bills_by_area(area: str):
    # 📅 today range
    today = datetime.utcnow().date()
    start = datetime(today.year, today.month, today.day)
    end = start + timedelta(days=1)

    # 1️⃣ find customers in area
    customers_cursor = customers_collection.find({"area": area})
    customers = []
    async for c in customers_cursor:
        customers.append(c)

    if not customers:
        return {"date": today.isoformat(), "orders": []}

    customer_ids = [c["_id"] for c in customers]

    # 2️⃣ find today's orders
    orders_cursor = orders_collection.find({
        "customer_id": {"$in": customer_ids},
        "created_at": {"$gte": start, "$lt": end}
    })

    results = []

    async for order in orders_cursor:
        bill = await bills_collection.find_one({"order_id": order["_id"]})
        if not bill:
            continue

        items_response = []

        for item in bill["items"]:
            items_response.append({
                "item_id": str(item["item_id"]),
                "item_name": item["item_name"],
                "quantity": item["quantity"],
                "price": item["price"],
                "total": item["total"]
            })

        results.append({
            "order_id": str(order["_id"]),
            "customer_id": str(order["customer_id"]),
            "created_at": order["created_at"],
            "bill_amount": bill["bill_amount"],
            "remaining_due": bill["new_due"],
            "items": items_response
        })

    return {
        "date": today.isoformat(),
        "total_orders": len(results),
        "orders": results
    }
