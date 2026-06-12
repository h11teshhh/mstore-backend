from app.database import orders_collection, customers_collection, bills_collection
from app.utils.ist_time import today_ist_utc_range, today_ist_date_str


async def get_today_bills_by_area(area: str):
    """
    Returns today's bills filtered by IST calendar date.
    'Today' means 00:00 IST → 23:59 IST of the current IST day.
    """
    start, end = today_ist_utc_range()

    results = []
    cursor  = orders_collection.find({
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
                "item_id":   str(item.get("item_id")),
                "item_name": item.get("item_name", ""),
                "quantity":  int(item.get("quantity", 0)),
                "price":     float(item.get("price", 0)),
                "total":     float(item.get("total", 0)),
            })

        new_due      = float(bill.get("new_due", 0))
        bill_amt     = float(bill.get("bill_amount", 0))
        order_status = order.get("status", "CREATED")

        if order_status == "CLOSED" or new_due == 0:
            payment_status = "PAID"
        elif new_due < bill_amt:
            payment_status = "PARTIAL"
        else:
            payment_status = "PENDING"

        results.append({
            "order_id":       str(order["_id"]),
            "customer_id":    str(customer["_id"]),
            "customer_name":  customer.get("name", ""),
            "created_at":     order.get("created_at"),
            "remaining_due":  new_due,
            "bill_amount":    bill_amt,
            "payment_status": payment_status,
            "order_status":   order_status,
            "items":          items,
        })

    return {
        "date":         today_ist_date_str(),
        "area":         area,
        "total_orders": len(results),
        "orders":       results,
    }
