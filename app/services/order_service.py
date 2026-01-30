from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException

from app.database import (
    orders_collection,
    inventory_collection,
    inventory_itemdetails_collection,
    customers_collection,
    bills_collection,
    client,
)
from app.services.inventory_stock_service import get_current_stock

async def get_orders_by_customer(customer_id: str):
    cursor = orders_collection.find({"customer_id": customer_id})
    orders = []

    async for order in cursor:
        order["id"] = str(order["_id"])
        del order["_id"]
        orders.append(order)

    return orders

async def create_order(data: dict, current_user: dict):
    async with await client.start_session() as session:
        async with session.start_transaction():

            # 1️⃣ Validate customer
            customer = await customers_collection.find_one(
                {"_id": ObjectId(data["customer_id"]), "is_active": True},
                session=session
            )
            if not customer:
                raise HTTPException(404, "Customer not found")

            previous_due = customer.get("current_due", 0)
            total_amount = 0
            items_snapshot = []

            # 2️⃣ Process items
            for item in data["items"]:
                item_id = ObjectId(item["item_id"])
                quantity = item["quantity"]

                if quantity <= 0:
                    raise HTTPException(400, "Quantity must be greater than zero")

                inventory_item = await inventory_collection.find_one(
                    {"_id": item_id, "is_active": True},
                    session=session
                )
                if not inventory_item:
                    raise HTTPException(404, "Inventory item not found")

                current_stock = await get_current_stock(str(item_id))
                if quantity > current_stock:
                    raise HTTPException(
                        400,
                        f"Insufficient stock for {inventory_item['item_name']}"
                    )

                price = inventory_item["price"]
                line_total = price * quantity
                total_amount += line_total

                items_snapshot.append({
                    "item_id": item_id,
                    "item_name": inventory_item["item_name"],
                    "quantity": quantity,
                    "price": price,
                    "total": line_total
                })

            # 3️⃣ Create order
            order_doc = {
                "customer_id": customer["_id"],
                "total_amount": total_amount,
                "status": "CREATED",
                "created_by": ObjectId(current_user["id"]),
                "created_by_role": current_user["role"],
                "created_at": datetime.utcnow()
            }

            order_result = await orders_collection.insert_one(
                order_doc,
                session=session
            )
            order_id = order_result.inserted_id

            # 4️⃣ Stock OUT
            for item in items_snapshot:
                await inventory_itemdetails_collection.insert_one(
                    {
                        "item_id": item["item_id"],
                        "quantity": item["quantity"],
                        "movement_type": "OUT",
                        "created_by": ObjectId(current_user["id"]),
                        "created_at": datetime.utcnow()
                    },
                    session=session
                )

            # 5️⃣ Bill
            new_due = previous_due + total_amount

            await bills_collection.insert_one(
                {
                    "order_id": order_id,
                    "customer_id": customer["_id"],
                    "items": items_snapshot,
                    "bill_amount": total_amount,
                    "previous_due": previous_due,
                    "new_due": new_due,
                    "created_at": datetime.utcnow()
                },
                session=session
            )

            # 6️⃣ Update customer due
            await customers_collection.update_one(
                {"_id": customer["_id"]},
                {
                    "$set": {
                        "current_due": new_due,
                        "updated_at": datetime.utcnow()
                    }
                },
                session=session
            )

            return {
                "order_id": str(order_id),
                "bill_amount": total_amount,
                "previous_due": previous_due,
                "new_due": new_due
            }
