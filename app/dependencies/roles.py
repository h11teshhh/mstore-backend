from fastapi import Depends, HTTPException
from app.dependencies.auth import get_current_user

def require_roles(*allowed_roles: str):
    async def role_checker(current_user=Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail="You are not allowed to perform this action"
            )
        return current_user
    return role_checker
