"""
payment_service.py  —  Single source of truth for all payment operations.

Order lifecycle:
  CREATED  →  bill.new_due == bill.bill_amount  (no payment yet)
  CREATED  →  0 < bill.new_due < bill.bill_amount  (partial payment)
  CLOSED   →  bill.new_due == 0  (fully paid)

Both customer_payment (from payments screen, needs area/bill selection)
and direct_customer_payment (from customer profile, any time) use the
same FIFO allocation logic so order statuses stay in sync.
"""

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


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL: FIFO bill allocator
# Shared by both customer_payment and direct_customer_payment.
# Returns (total_paid, bills_settled_list) and performs all DB writes
# inside the given session.
# ─────────────────────────────────────────────────────────────────────────────
async def _allocate_fifo(
    customer_obj_id: ObjectId,
    user_obj_id: ObjectId,
    current_user: dict,
    amount: float,
    payment_type: str,
    session,
    note: str = "",
) -> tuple[float, list]:
    """
    Allocates `amount` across unpaid bills for the customer (oldest first).
    Writes payment records and updates bill.new_due + order.status.
    Returns (total_allocated, bills_settled).
    Does NOT update customer.current_due — caller does that.
    """
    remaining = float(amount)
    total_allocated = 0.0
    bills_settled   = []
    now             = datetime.utcnow()

    cursor = (
        bills_collection
        .find(
            {"customer_id": customer_obj_id, "new_due": {"$gt": 0}},
            session=session,
        )
        .sort("created_at", 1)   # oldest bill first — FIFO
    )

    async for bill in cursor:
        if remaining <= 0:
            break

        bill_due    = float(bill.get("new_due", 0))
        if bill_due <= 0:
            continue

        pay_amount   = min(bill_due, remaining)
        new_bill_due = round(bill_due - pay_amount, 2)

        payment_status = "COMPLETE" if new_bill_due == 0 else "PARTIAL"

        # Payment record per bill
        payment_doc = {
            "order_id":       bill.get("order_id"),
            "customer_id":    customer_obj_id,
            "amount":         pay_amount,
            "payment_type":   payment_type,
            "payment_method": "CASH",
            "received_by": {
                "id":   user_obj_id,
                "role": current_user.get("role"),
                "name": current_user.get("name"),
            },
            "payment_status": payment_status,
            "created_by":     user_obj_id,
            "created_at":     now,
        }
        if note:
            payment_doc["note"] = note

        await payments_collection.insert_one(payment_doc, session=session)

        # Update bill remaining due
        await bills_collection.update_one(
            {"_id": bill["_id"]},
            {"$set": {"new_due": new_bill_due, "updated_at": now}},
            session=session,
        )

        # Close order when fully paid
        if new_bill_due == 0 and bill.get("order_id"):
            await orders_collection.update_one(
                {"_id": bill["order_id"]},
                {"$set": {"status": "CLOSED", "closed_at": now, "updated_at": now}},
                session=session,
            )

        remaining       -= pay_amount
        total_allocated += pay_amount

        bills_settled.append({
            "order_id":     str(bill.get("order_id")) if bill.get("order_id") else None,
            "paid":         pay_amount,
            "remaining_due":new_bill_due,
            "status":       payment_status,
        })

    return total_allocated, bills_settled


# ─────────────────────────────────────────────────────────────────────────────
# GET PAYMENTS BY CUSTOMER
# ─────────────────────────────────────────────────────────────────────────────
async def get_payments_by_customer(customer_id: str):
    try:
        customer_obj_id = ObjectId(customer_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid customer_id")

    payments = []
    cursor   = (
        payments_collection
        .find({"customer_id": customer_obj_id})
        .sort("created_at", -1)   # newest first in profile view
    )

    async for p in cursor:
        received_by = p.get("received_by", {})
        payments.append({
            "id":             str(p["_id"]),
            "order_id":       str(p["order_id"]) if p.get("order_id") else None,
            "customer_id":    str(p["customer_id"]),
            "amount":         float(p.get("amount", 0)),
            "payment_status": p.get("payment_status"),
            "payment_type":   p.get("payment_type", "CUSTOMER_PAYMENT"),
            "note":           p.get("note", ""),
            "received_by": {
                "id":   str(received_by["id"]) if received_by.get("id") else None,
                "role": received_by.get("role"),
                "name": received_by.get("name"),
            },
            "created_at": p.get("created_at"),
        })

    return payments


# ─────────────────────────────────────────────────────────────────────────────
# CUSTOMER PAYMENT  (from Payments screen — area/bill based)
# ─────────────────────────────────────────────────────────────────────────────
async def customer_payment(customer_id: str, amount: float, current_user: dict):
    if amount < 0:
        raise HTTPException(status_code=400, detail="Payment amount cannot be negative")
    if amount == 0:
        return {"message": "Zero payment — no changes made",
                "entered_amount": 0, "accepted_amount": 0, "bills_settled": []}

    try:
        customer_obj_id = ObjectId(customer_id)
        user_obj_id     = ObjectId(current_user["id"])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    async with await client.start_session() as session:
        async with session.start_transaction():

            customer = await customers_collection.find_one(
                {"_id": customer_obj_id}, session=session)
            if not customer:
                raise HTTPException(status_code=404, detail="Customer not found")

            current_due = float(customer.get("current_due", 0))
            if current_due <= 0:
                raise HTTPException(status_code=400, detail="Customer has no pending dues")
            if amount > current_due:
                raise HTTPException(
                    status_code=400,
                    detail=f"Amount ₹{amount:.0f} exceeds outstanding due ₹{current_due:.0f}",
                )

            total_allocated, bills_settled = await _allocate_fifo(
                customer_obj_id, user_obj_id, current_user,
                amount, "CUSTOMER_PAYMENT", session,
            )

            # If payment amount exceeds all bill dues (shouldn't happen but safety net)
            # record remainder as a standalone payment with no order_id
            unallocated = round(amount - total_allocated, 2)
            if unallocated > 0:
                now = datetime.utcnow()
                await payments_collection.insert_one({
                    "order_id":       None,
                    "customer_id":    customer_obj_id,
                    "amount":         unallocated,
                    "payment_type":   "CUSTOMER_PAYMENT",
                    "payment_method": "CASH",
                    "received_by": {
                        "id":   user_obj_id,
                        "role": current_user.get("role"),
                        "name": current_user.get("name"),
                    },
                    "payment_status": "COMPLETE",
                    "created_by":     user_obj_id,
                    "created_at":     now,
                }, session=session)
                total_allocated += unallocated

            # Update customer running due
            now = datetime.utcnow()
            await customers_collection.update_one(
                {"_id": customer_obj_id},
                {"$inc": {"current_due": -total_allocated},
                 "$set": {"updated_at": now}},
                session=session,
            )

            return {
                "message":        "Payment received successfully",
                "entered_amount": amount,
                "accepted_amount":total_allocated,
                "remaining_due":  max(current_due - total_allocated, 0),
                "bills_settled":  bills_settled,
            }


# ─────────────────────────────────────────────────────────────────────────────
# DIRECT PAYMENT  (from Customer Profile — works anytime, no bill required)
# Also uses FIFO allocation so order statuses stay accurate.
# ─────────────────────────────────────────────────────────────────────────────
async def direct_customer_payment(
    customer_id: str, amount: float, note: str, current_user: dict
):
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")

    try:
        customer_obj_id = ObjectId(customer_id)
        user_obj_id     = ObjectId(current_user["id"])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    # Pre-check before transaction
    customer_pre = await customers_collection.find_one({"_id": customer_obj_id})
    if not customer_pre:
        raise HTTPException(status_code=404, detail="Customer not found")
    current_due_pre = float(customer_pre.get("current_due", 0))
    if current_due_pre <= 0:
        raise HTTPException(status_code=400, detail="Customer has no outstanding dues")
    if amount > current_due_pre:
        raise HTTPException(
            status_code=400,
            detail=f"Payment ₹{amount:.0f} exceeds outstanding due ₹{current_due_pre:.0f}",
        )

    async with await client.start_session() as session:
        async with session.start_transaction():

            customer = await customers_collection.find_one(
                {"_id": customer_obj_id}, session=session)
            if not customer:
                raise HTTPException(status_code=404, detail="Customer not found")

            current_due = float(customer.get("current_due", 0))

            # FIFO allocation across unpaid bills (same logic as customer_payment)
            total_allocated, bills_settled = await _allocate_fifo(
                customer_obj_id, user_obj_id, current_user,
                amount, "DIRECT_PAYMENT", session, note=note,
            )

            # If no bills exist at all (rare edge case), record one standalone payment
            if total_allocated == 0:
                now = datetime.utcnow()
                await payments_collection.insert_one({
                    "order_id":       None,
                    "customer_id":    customer_obj_id,
                    "amount":         amount,
                    "note":           note or "",
                    "payment_type":   "DIRECT_PAYMENT",
                    "payment_method": "CASH",
                    "received_by": {
                        "id":   user_obj_id,
                        "role": current_user.get("role"),
                        "name": current_user.get("name"),
                    },
                    "payment_status": "COMPLETE",
                    "created_by":     user_obj_id,
                    "created_at":     now,
                }, session=session)
                total_allocated = amount

            # Update customer running due
            now     = datetime.utcnow()
            new_due = max(current_due - total_allocated, 0)
            await customers_collection.update_one(
                {"_id": customer_obj_id},
                {"$set": {"current_due": new_due, "updated_at": now}},
                session=session,
            )

            return {
                "message":        "Payment recorded successfully",
                "amount_paid":    total_allocated,
                "previous_due":   current_due,
                "new_due":        new_due,
                "bills_settled":  bills_settled,
            }
