from typing import Callable

from fastapi import Depends, HTTPException, Request


# Role constants
PLATFORM_ADMIN = "Platform Admin"
TENANT_ADMIN = "Tenant Admin"
MEMBER = "Member"
VIEWER = "Viewer"


async def get_current_user(request: Request) -> dict:
    user_context = getattr(request.state, "user_context", None)
    if not user_context:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_context


def require_role(role: str) -> Callable:
    async def _check_role(current_user: dict = Depends(get_current_user)) -> dict:
        if role not in current_user.get("roles", []):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return _check_role


def require_any_role(*roles: str) -> Callable:
    async def _check_any_role(current_user: dict = Depends(get_current_user)) -> dict:
        user_roles = current_user.get("roles", [])
        if not any(r in user_roles for r in roles):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return _check_any_role
