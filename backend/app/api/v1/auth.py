from fastapi import APIRouter, Depends

from app.api.v1.dependencies import get_current_user

router = APIRouter()


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["user_id"],
        "email": current_user["email"],
        "full_name": current_user["name"],
        "tenant_id": current_user["tenant_id"],
        "roles": current_user["roles"],
    }
