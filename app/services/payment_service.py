from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException

from app.database import (
    customers_collection,
    payments_collection,
    orders_collection,
    bills_collection,
)


# -------------------------
# GET PAYMENTS BY CUSTOMER
# -------------------------
async def get_payments_by_customer(customer_id: str):
    try:
        customer_obj_id = ObjectId(customer_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid customer_id")

    cursor = payments_collection.find({"customer_id": customer_obj_id})

    payments = []
    async for payment in cursor:
        payments.append({
            "id": str(payment["_id"]),
            "order_id": str(payment.get("order_id")),
            "customer_id": str(payment.get("customer_id")),
            "amount": payment.get("amount"),
            "payment_type": payment.get("type"),
            "received_by": payment.get("received_by"),
            "created_by": str(payment.get("created_by")),
            "created_at": payment.get("created_at"),
        })

    return payments


# -------------------------
# COMPLETE PAYMENT
# -------------------------
async def complete_payment(order_id: str, customer_id: str, current_user_id: str):
    try:
        order_obj_id = ObjectId(order_id)
        customer_obj_id = ObjectId(customer_id)
        user_obj_id = ObjectId(current_user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    bill = await bills_collection.find_one({"order_id": order_obj_id})
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    if bill.get("new_due", 0) <= 0:
        raise HTTPException(status_code=400, detail="Bill already settled")

    amount = bill["new_due"]

    # Save payment
    await payments_collection.insert_one({
        "order_id": order_obj_id,
        "customer_id": customer_obj_id,
        "amount": amount,
        "type": "FULL",
        "received_by": "delivery",
        "created_by": user_obj_id,
        "created_at": datetime.utcnow(),
    })

    # Update bill
    await bills_collection.update_one(
        {"_id": bill["_id"]},
        {"$set": {"new_due": 0}}
    )

    # Update customer due and activity
    await customers_collection.update_one(
        {"_id": customer_obj_id},
        {
            "$inc": {"current_due": -amount},
            "$set": {"updated_at": datetime.utcnow()},
        },
    )

    # Close order
    await orders_collection.update_one(
        {"_id": order_obj_id},
        {"$set": {"status": "CLOSED", "closed_at": datetime.utcnow()}},
    )

    return {
        "message": "Full payment received",
        "paid": amount,
        "remaining_due": 0,
    }


# -------------------------
# PARTIAL PAYMENT
# -------------------------
async def partial_payment(order_id: str, customer_id: str, amount: float, current_user_id: str):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid payment amount")

    try:
        order_obj_id = ObjectId(order_id)
        customer_obj_id = ObjectId(customer_id)
        user_obj_id = ObjectId(current_user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    bill = await bills_collection.find_one({"order_id": order_obj_id})
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    if amount > bill.get("new_due", 0):
        raise HTTPException(status_code=400, detail="Payment exceeds bill due")

    new_due = bill["new_due"] - amount

    # Save payment
    await payments_collection.insert_one({
        "order_id": order_obj_id,
        "customer_id": customer_obj_id,
        "amount": amount,
        "type": "PARTIAL",
        "received_by": "delivery",
        "created_by": user_obj_id,
        "created_at": datetime.utcnow(),
    })

    # Update bill
    await bills_collection.update_one(
        {"_id": bill["_id"]},
        {"$set": {"new_due": new_due}},
    )

    # Update customer due and activity
    await customers_collection.update_one(
        {"_id": customer_obj_id},
        {
            "$inc": {"current_due": -amount},
            "$set": {"updated_at": datetime.utcnow()},
        },
    )

    # Update order status
    await orders_collection.update_one(
        {"_id": order_obj_id},
        {"$set": {"status": "DELIVERED", "delivered_at": datetime.utcnow()}},
    )

    return {
        "message": "Partial payment received",
        "paid": amount,
        "remaining_due": new_due,
    }
