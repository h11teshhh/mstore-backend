from fastapi import APIRouter, Depends
from app.schemas.user import UserCreate
from app.services.user_service import create_user
from app.dependencies.roles import require_roles

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/")
async def create_new_user(
    data: UserCreate,
    current_user=Depends(require_roles("SUPERADMIN"))
):
    return await create_user(data.dict(), current_user)
