from app.database import (
    bills_collection,
    payments_collection,
    inventory_collection,
    customers_collection,
)
from app.utils.ist_time import today_ist_utc_range, today_ist_date_str


async def end_of_day_summary():
    """
    End-of-day report for the current IST calendar day.
    Uses IST midnight boundaries so the day resets correctly at 12:00 AM IST.
    """
    start, end = today_ist_utc_range()

    # ── 1. Stock sold today (item-wise) ──────────────────────────────────────
    stock_pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lt": end}}},
        {"$unwind": "$items"},
        {"$group": {"_id": "$items.item_id", "quantity_sold": {"$sum": "$items.quantity"}}},
    ]
    stock_sold = []
    async for s in bills_collection.aggregate(stock_pipeline):
        item = await inventory_collection.find_one({"_id": s["_id"]})
        stock_sold.append({
            "item_name":     item["item_name"] if item else "Unknown",
            "quantity_sold": s["quantity_sold"],
        })

    # ── 2. Total cash received today ──────────────────────────────────────────
    payment_pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lt": end}}},
        {"$group": {"_id": None, "total_cash": {"$sum": "$amount"}}},
    ]
    payment_result = await payments_collection.aggregate(payment_pipeline).to_list(1)
    total_cash     = payment_result[0]["total_cash"] if payment_result else 0

    # ── 3. Customer-wise ledger ───────────────────────────────────────────────
    customer_pipeline = [
        {"$match": {"created_at": {"$gte": start, "$lt": end}}},
        {"$group": {"_id": "$customer_id", "paid_today": {"$sum": "$amount"}}},
    ]
    customer_ledger = []
    async for c in payments_collection.aggregate(customer_pipeline):
        customer = await customers_collection.find_one({"_id": c["_id"]})
        if not customer:
            continue
        remaining_due = float(customer.get("current_due", 0))
        paid_today    = float(c["paid_today"])
        previous_due  = remaining_due + paid_today
        customer_ledger.append({
            "customer_name": customer["name"],
            "previous_due":  previous_due,
            "paid_today":    paid_today,
            "remaining_due": remaining_due,
        })

    return {
        "date":                    today_ist_date_str(),
        "stock_sold":              stock_sold,
        "cash_received_today":     total_cash,
        "delivery_cash_expected":  total_cash,
        "customers":               customer_ledger,
    }
