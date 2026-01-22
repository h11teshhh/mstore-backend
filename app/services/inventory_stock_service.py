from bson import ObjectId
from app.database import inventory_collection, inventory_itemdetails_collection


# 🔹 Get current stock for ONE item (used during order validation)
async def get_current_stock(item_id: str) -> int:
    pipeline = [
        {"$match": {"item_id": ObjectId(item_id)}},
        {
            "$group": {
                "_id": "$item_id",
                "in_qty": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$movement_type", "IN"]},
                            "$quantity",
                            0
                        ]
                    }
                },
                "out_qty": {
                    "$sum": {
                        "$cond": [
                            {"$eq": ["$movement_type", "OUT"]},
                            "$quantity",
                            0
                        ]
                    }
                }
            }
        }
    ]

    result = await inventory_itemdetails_collection.aggregate(pipeline).to_list(1)

    if not result:
        return 0

    return result[0]["in_qty"] - result[0]["out_qty"]


# 🔹 Get ALL inventory items with current stock (UI warehouse screen)
async def get_inventory_with_stock():
    pipeline = [
        {
            "$lookup": {
                "from": "inventory_itemdetails",
                "localField": "_id",
                "foreignField": "item_id",
                "as": "movements"
            }
        },
        {
            "$addFields": {
                "current_stock": {
                    "$subtract": [
                        {
                            "$sum": {
                                "$map": {
                                    "input": {
                                        "$filter": {
                                            "input": "$movements",
                                            "as": "m",
                                            "cond": {"$eq": ["$$m.movement_type", "IN"]}
                                        }
                                    },
                                    "as": "i",
                                    "in": "$$i.quantity"
                                }
                            }
                        },
                        {
                            "$sum": {
                                "$map": {
                                    "input": {
                                        "$filter": {
                                            "input": "$movements",
                                            "as": "m",
                                            "cond": {"$eq": ["$$m.movement_type", "OUT"]}
                                        }
                                    },
                                    "as": "o",
                                    "in": "$$o.quantity"
                                }
                            }
                        }
                    ]
                }
            }
        },
        {
            "$project": {
                "movements": 0
            }
        }
    ]

    items = []
    async for item in inventory_collection.aggregate(pipeline):
        if not item.get("is_active", True):
            continue

        items.append({
            "id": str(item["_id"]),
            "item_name": item["item_name"],
            "price": item["price"],
            "current_stock": item.get("current_stock", 0),
            "is_active": item["is_active"]
        })

    return items
