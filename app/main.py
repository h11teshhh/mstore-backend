from fastapi import FastAPI
from app.routes.inventory_routes import router as inventory_router
from app.routes.inventory_itemdetails_routes import router as inventory_movement_router
from app.routes.order_routes import router as order_router
from app.routes.stock_adjustment_routes import router as stock_adjustment_router
from app.routes.order_report_routes import router as order_report_router
from app.utils.db_indexes import create_indexes
from app.routes.customer_routes import router as customer_router
from app.routes.truck_load_routes import router as truck_load_router
from app.routes.payment_routes import router as payment_router 
from app.routes.end_of_day_routes import router as end_of_day_router
from app.routes.auth_routes import router as auth_router
from app.routes.user_routes import router as user_router
from app.services.auth_service import create_superadmin

from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(title="Mstore Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later restrict
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



app.include_router(inventory_router)
app.include_router(inventory_movement_router)
app.include_router(order_router)
app.include_router(stock_adjustment_router)
app.include_router(order_report_router)
app.include_router(customer_router)
app.include_router(truck_load_router)
app.include_router(payment_router)
app.include_router(end_of_day_router)
app.include_router(auth_router)
app.include_router(user_router)


@app.on_event("startup")
async def startup():
    await create_superadmin()
    
@app.on_event("startup")
async def startup():
    await create_indexes()
    
@app.get("/")
def root():
    return {"message": "Mstore backend is running"}
