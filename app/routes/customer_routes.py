from fastapi import APIRouter
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse
)
from app.services.customer_service import (
    create_customer,
    get_all_customers,
    update_customer
)

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post("/", response_model=CustomerResponse)
async def add_customer(customer: CustomerCreate):
    return await create_customer(customer.dict())


@router.get("/", response_model=list[CustomerResponse])
async def list_customers():
    return await get_all_customers()


@router.put("/{customer_id}")
async def edit_customer(customer_id: str, customer: CustomerUpdate):
    return await update_customer(customer_id, customer.dict())
