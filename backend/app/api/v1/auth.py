from fastapi import APIRouter, Depends, Request

from app.api.v1.dependencies import get_current_user
from app.repositories.tenant_repo import TenantRepository

router = APIRouter()


@router.get("/me")
async def me(request: Request, current_user: dict = Depends(get_current_user)):
    roles = list(current_user["roles"])
    user_email = current_user["email"].lower()
    user_groups = set(current_user.get("groups", []))

    # Resolve accessible platform tenants from group membership or admin email
    tenant_repo = TenantRepository()
    all_tenants = await tenant_repo.list_all_tenants()

    accessible_tenants = []
    for t in all_tenants:
        if t.get("status") == "deleted":
            continue
        # Match by Entra group assignment
        group_id = t.get("entra_group_id")
        if group_id and group_id in user_groups:
            accessible_tenants.append(
                {"id": t["id"], "name": t["name"], "slug": t["slug"], "role": "member"}
            )
        # Match by admin email
        elif t.get("admin_email", "").lower() == user_email:
            accessible_tenants.append(
                {"id": t["id"], "name": t["name"], "slug": t["slug"], "role": "admin"}
            )

    return {
        "id": current_user["user_id"],
        "email": current_user["email"],
        "full_name": current_user["name"],
        "tenant_id": current_user["tenant_id"],
        "roles": roles,
        "accessible_tenants": accessible_tenants,
    }
