from app.database import (
    inventory_collection,
    customers_collection,
    orders_collection,
    users_collection,
    bills_collection,
    payments_collection,
)


async def create_indexes():
    # ── Users ─────────────────────────────────────────────────────────────
    # mobile index: login_user() does find({"mobile": ...}) on every login
    # Without this index every login is a full collection scan → slow first login
    await users_collection.create_index("mobile", unique=True, sparse=True)

    # ── Inventory ─────────────────────────────────────────────────────────
    await inventory_collection.create_index("item_name", unique=True)

    # ── Customers ─────────────────────────────────────────────────────────
    await customers_collection.create_index("mobile", unique=True)
    await customers_collection.create_index("area")           # area filter in bills/reports

    # ── Orders ────────────────────────────────────────────────────────────
    await orders_collection.create_index("created_at")        # date range queries
    await orders_collection.create_index("customer_id")       # get_orders_by_customer
    await orders_collection.create_index("status")            # FIFO payment queries

    # ── Bills ─────────────────────────────────────────────────────────────
    await bills_collection.create_index("order_id")           # bill lookup per order
    await bills_collection.create_index("customer_id")        # FIFO allocator query
    # Compound index for FIFO: customer_id + new_due + created_at (oldest unpaid first)
    await bills_collection.create_index([
        ("customer_id", 1),
        ("new_due", 1),
        ("created_at", 1),
    ])

    # ── Payments ──────────────────────────────────────────────────────────
    await payments_collection.create_index("customer_id")     # get_payments_by_customer
    await payments_collection.create_index("created_at")      # daily payment reports
