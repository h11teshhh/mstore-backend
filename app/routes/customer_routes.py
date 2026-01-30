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
