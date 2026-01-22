from datetime import datetime, timedelta
from app.database import bills_collection, inventory_collection


async def get_today_truck_load():
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lt": end}}},
        {"$unwind": "$items"},
        {
            "$group": {
                "_id": "$items.item_id",
                "total_quantity": {"$sum": "$items.quantity"}
            }
        }
    ]

    result = []
    async for r in bills_collection.aggregate(pipeline):
        item = await inventory_collection.find_one({"_id": r["_id"]})
        result.append({
            "item_id": str(r["_id"]),
            "item_name": item["item_name"] if item else "Unknown",
            "quantity_to_load": r["total_quantity"]
        })

    return {
        "date": start.date().isoformat(),
        "items": result
    }
