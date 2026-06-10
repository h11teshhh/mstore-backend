from fastapi import APIRouter, Depends, HTTPException
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse
)
from app.services.customer_service import (
    create_customer,
    get_all_customers,
    get_customer_by_id,
    update_customer
)
from app.dependencies.auth import get_current_user
from app.database import customers_collection
from datetime import datetime

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post("/", response_model=CustomerResponse)
async def add_customer(
    customer: CustomerCreate,
    current_user: dict = Depends(get_current_user)
):
    if current_user["role"] != "SUPERADMIN":
        raise HTTPException(status_code=403, detail="Only SUPERADMIN can create customers")

    return await create_customer(customer.dict(), current_user["id"])


@router.get("/", response_model=list[CustomerResponse])
async def list_customers():
    return await get_all_customers()


@router.get("/{customer_id}/", response_model=CustomerResponse)
async def get_customer(customer_id: str):
    return await get_customer_by_id(customer_id)


@router.put("/{customer_id}")
async def edit_customer(customer_id: str, customer: CustomerUpdate):
    return await update_customer(customer_id, customer.dict())


# DELETE endpoint for SUPERADMIN - soft delete to avoid breaking orders, bills, reports
@router.delete("/{customer_id}", dependencies=[Depends(get_current_user)])
async def delete_customer(customer_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "SUPERADMIN":
        raise HTTPException(status_code=403, detail="Only SUPERADMIN can delete customers")
    
    if customers_collection is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    
    from bson import ObjectId
    try:
        obj_id = ObjectId(customer_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid customer ID")
    
    customer = await customers_collection.find_one({"_id": obj_id})
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    
    # Soft delete - set is_active=False (adds field if missing, preserves data for reports)
    result = await customers_collection.update_one(
        {"_id": obj_id},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
    )
    
    if result.modified_count == 0:
        # If already inactive or no change
        pass
    
    return {"message": "Customer deleted successfully (deactivated). Existing orders and records preserved.", "customer_id": customer_id}
