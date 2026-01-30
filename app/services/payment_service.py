from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException

from app.database import (
    customers_collection,
    payments_collection,
    orders_collection,
    bills_collection,
)



async def get_payments_by_customer(customer_id: str):
    cursor = payments_collection.find({"customer_id": customer_id})
    payments = []

    async for payment in cursor:
        payment["id"] = str(payment["_id"])
        del payment["_id"]
        payments.append(payment)

    return payments

async def complete_payment(order_id: str, customer_id: str, current_user_id: str):
    bill = await bills_collection.find_one({"order_id": ObjectId(order_id)})

    if not bill:
        raise HTTPException(404, "Bill not found")

    if bill["new_due"] <= 0:
        raise HTTPException(400, "Bill already settled")

    amount = bill["new_due"]

    # Save payment
    await payments_collection.insert_one({
        "order_id": ObjectId(order_id),
        "customer_id": ObjectId(customer_id),
        "amount": amount,
        "type": "FULL",
        "received_by": "delivery",
        "created_by": ObjectId(current_user_id),
        "created_at": datetime.utcnow()
    })

    # Update bill
    await bills_collection.update_one(
        {"_id": bill["_id"]},
        {"$set": {"new_due": 0}}
    )

    # Update customer due
    await customers_collection.update_one(
        {"_id": ObjectId(customer_id)},
        {"$inc": {"current_due": -amount}}
    )

    # Close order
    await orders_collection.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"status": "CLOSED", "closed_at": datetime.utcnow()}}
    )

    return {
        "message": "Full payment received",
        "paid": amount,
        "remaining_due": 0
    }


async def partial_payment(order_id: str, customer_id: str, amount: float, current_user_id: str):
    if amount <= 0:
        raise HTTPException(400, "Invalid payment amount")

    bill = await bills_collection.find_one({"order_id": ObjectId(order_id)})

    if not bill:
        raise HTTPException(404, "Bill not found")

    if amount > bill["new_due"]:
        raise HTTPException(400, "Payment exceeds bill due")

    new_due = bill["new_due"] - amount

    # Save payment
    await payments_collection.insert_one({
        "order_id": ObjectId(order_id),
        "customer_id": ObjectId(customer_id),
        "amount": amount,
        "type": "PARTIAL",
        "received_by": "delivery",
        "created_by": ObjectId(current_user_id),
        "created_at": datetime.utcnow()
    })

    # Update bill
    await bills_collection.update_one(
        {"_id": bill["_id"]},
        {"$set": {"new_due": new_due}}
    )

    # Update customer due
    await customers_collection.update_one(
        {"_id": ObjectId(customer_id)},
        {"$inc": {"current_due": -amount}}
    )

    # Update order status
    await orders_collection.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"status": "DELIVERED", "delivered_at": datetime.utcnow()}}
    )

    return {
        "message": "Partial payment received",
        "paid": amount,
        "remaining_due": new_due
    }
