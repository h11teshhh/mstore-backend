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
            {"_id": order.get("customer_id"), "area": area}
        )

        if not customer:
            continue

        bill = await bills_collection.find_one({"order_id": order["_id"]})
        if not bill:
            continue

        items = []
        for item in bill.get("items", []):
            items.append({
                "item_id": str(item.get("item_id")),
                "item_name": item.get("item_name", ""),
                "quantity": int(item.get("quantity", 0)),
                "price": float(item.get("price", 0)),
                "total": float(item.get("total", 0)),
            })

        results.append({
            "order_id": str(order["_id"]),
            "customer_id": str(customer["_id"]),
            "customer_name": customer.get("name", ""),
            "created_at": order.get("created_at"),
            "remaining_due": float(bill.get("new_due", 0)),   # ✅ per order
            "bill_amount": float(bill.get("bill_amount", 0)),
            "items": items,
        })

    return {
        "date": start.date().isoformat(),
        "area": area,
        "total_orders": len(results),
        "orders": results,
    }
