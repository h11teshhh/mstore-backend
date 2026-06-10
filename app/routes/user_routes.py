from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.user import UserCreate
from app.services.user_service import create_user
from app.dependencies.roles import require_roles
from app.database import users_collection
from datetime import datetime

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/")
async def create_new_user(
    data: UserCreate,
    current_user=Depends(require_roles("SUPERADMIN"))
):
    return await create_user(data.dict(), current_user)


# DELETE for SUPERADMIN - soft delete to preserve referential integrity, reports, calculations
@router.delete("/{user_id}", dependencies=[Depends(require_roles("SUPERADMIN"))])
async def delete_user(user_id: str):
    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database unavailable")
    
    from bson import ObjectId
    try:
        obj_id = ObjectId(user_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid user ID format")
    
    user = await users_collection.find_one({"_id": obj_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.get("role") == "SUPERADMIN":
        # Prevent deleting the last superadmin or self, but for simplicity check active superadmins
        active_superadmins = await users_collection.count_documents({"role": "SUPERADMIN", "is_active": True})
        if active_superadmins <= 1:
            raise HTTPException(status_code=400, detail="Cannot delete the last active SUPERADMIN account.")
    
    # Soft delete
    result = await users_collection.update_one(
        {"_id": obj_id},
        {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Failed to delete user or already inactive")
    
    return {"message": "User deleted successfully (deactivated)", "user_id": user_id}
