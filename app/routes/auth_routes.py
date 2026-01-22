from fastapi import APIRouter
from app.schemas.user import UserLogin
from app.services.auth_service import login_user

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login")
async def login(data: UserLogin):
    return await login_user(data.mobile, data.password)
