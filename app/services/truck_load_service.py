from app.database import bills_collection, inventory_collection
from app.utils.ist_time import today_ist_utc_range, today_ist_date_str


async def get_today_truck_load():
    """
    Returns today's truck load using IST calendar date boundaries.
    """
    start, end = today_ist_utc_range()

    pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lt": end}}},
        {"$unwind": "$items"},
        {"$group": {"_id": "$items.item_id", "total_quantity": {"$sum": "$items.quantity"}}},
    ]

    result = []
    async for r in bills_collection.aggregate(pipeline):
        item = await inventory_collection.find_one({"_id": r["_id"]})
        result.append({
            "item_id":          str(r["_id"]),
            "item_name":        item["item_name"] if item else "Unknown",
            "quantity_to_load": r["total_quantity"],
        })

    return {
        "date":  today_ist_date_str(),
        "items": result,
    }
