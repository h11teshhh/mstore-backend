from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException

from app.database import (
    customers_collection,
    payments_collection,
    orders_collection,
    bills_collection,
    client,
)

# -------------------------------------------------
# CUSTOMER PAYMENT (FIFO – SINGLE SOURCE OF TRUTH)
# -------------------------------------------------
async def customer_payment(customer_id: str, amount: float, current_user: dict):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid payment amount")

    try:
        customer_obj_id = ObjectId(customer_id)
        user_obj_id = ObjectId(current_user["id"])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    now = datetime.utcnow()

    async with await client.start_session() as session:
        async with session.start_transaction():

            # 1️⃣ Fetch customer
            customer = await customers_collection.find_one(
                {"_id": customer_obj_id},
                session=session
            )

            if not customer:
                raise HTTPException(status_code=404, detail="Customer not found")

            current_due = float(customer.get("current_due", 0))

            if current_due <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Customer has no pending dues"
                )

            if amount > current_due:
                raise HTTPException(
                    status_code=400,
                    detail=f"Entered amount ₹{amount} exceeds pending due ₹{current_due}"
                )

            remaining_amount = amount
            total_paid = 0
            bills_settled = []

            # 2️⃣ Fetch unpaid bills FIFO (oldest first)
            cursor = (
                bills_collection
                .find(
                    {
                        "customer_id": customer_obj_id,
                        "new_due": {"$gt": 0}
                    },
                    session=session
                )
                .sort("created_at", 1)
            )

            async for bill in cursor:
                if remaining_amount <= 0:
                    break

                bill_due = float(bill.get("new_due", 0))
                if bill_due <= 0:
                    continue

                pay_amount = min(bill_due, remaining_amount)
                new_bill_due = bill_due - pay_amount

                payment_status = (
                    "COMPLETE" if new_bill_due == 0 else "PARTIAL"
                )

                # 3️⃣ Insert payment record (per bill)
                await payments_collection.insert_one(
                    {
                        "order_id": bill.get("order_id"),
                        "customer_id": customer_obj_id,
                        "amount": pay_amount,
                        "type": current_user.get("role"),  # who performed action
                        "received_by": {
                            "id": user_obj_id,
                            "role": current_user.get("role"),
                            "name": current_user.get("name"),
                        },
                        "payment_status": payment_status,
                        "created_by": user_obj_id,
                        "created_at": now,
                    },
                    session=session
                )

                # 4️⃣ Update bill due
                await bills_collection.update_one(
                    {"_id": bill["_id"]},
                    {"$set": {"new_due": new_bill_due}},
                    session=session
                )

                # 5️⃣ Close order if bill fully paid
                if new_bill_due == 0 and bill.get("order_id"):
                    await orders_collection.update_one(
                        {"_id": bill["order_id"]},
                        {
                            "$set": {
                                "status": "CLOSED",
                                "closed_at": now,
                            }
                        },
                        session=session
                    )

                remaining_amount -= pay_amount
                total_paid += pay_amount

                bills_settled.append({
                    "order_id": str(bill.get("order_id")),
                    "paid": pay_amount,
                    "status": payment_status,
                })

            if total_paid == 0:
                raise HTTPException(
                    status_code=400,
                    detail="No unpaid bills found for customer"
                )

            # 6️⃣ Update customer running due (ONCE)
            await customers_collection.update_one(
                {"_id": customer_obj_id},
                {
                    "$inc": {"current_due": -total_paid},
                    "$set": {"updated_at": now},
                },
                session=session
            )

            return {
                "message": "Payment received successfully",
                "entered_amount": amount,
                "accepted_amount": total_paid,
                "remaining_due": current_due - total_paid,
                "bills_settled": bills_settled,
            }