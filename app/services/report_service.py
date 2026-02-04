from datetime import datetime, timedelta
from bson import ObjectId
from app.database import orders_collection, customers_collection, bills_collection


async def get_today_bills_by_area(area: str):
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    results = []

    cursor = orders_collection.find({
        "created_at": {"$gte": start, "$lt": end}
    })

    async for order in cursor:
        customer = await customers_collection.find_one(
            {"_id": order["customer_id"], "area": area}
        )

        if not customer:
            continue  # skip if customer not in selected area

        bill = await bills_collection.find_one({"order_id": order["_id"]})

        if not bill:
            continue

        items = []
        for item in bill["items"]:
            items.append({
                "item_id": str(item["item_id"]),
                "item_name": item["item_name"],
                "quantity": item["quantity"],
                "price": item["price"],
                "total": item["total"]
            })

        results.append({
            "order_id": str(order["_id"]),
            "customer_id": str(customer["_id"]),
            "customer_name": customer["name"],   # ✅ now safe
            "created_at": order["created_at"],
            "remaining_due": bill["new_due"],
            "bill_amount": bill["total_amount"],
            "items": items
        })

    return {
        "date": start.date().isoformat(),
        "area": area,
        "orders": results
    }
