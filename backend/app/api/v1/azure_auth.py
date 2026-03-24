"""Azure Device Code authentication flow.

Uses Azure CLI's well-known public client ID (no app registration required).
Flow:
  1. POST /azure/auth/device-code  → returns user_code + verification_uri
  2. User opens verification_uri, enters user_code, signs in
  3. POST /azure/auth/device-code/token  → polls for token, returns access_token
"""

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Azure PowerShell public client ID — registered by Microsoft, works for any tenant
AZURE_CLIENT_ID = "1950a258-227b-4e31-a9cf-717495945fc2"
AZURE_MANAGEMENT_SCOPE = "https://management.azure.com/.default"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
DEVICE_CODE_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/devicecode"


class DeviceCodeResponse(BaseModel):
    user_code: str
    verification_uri: str
    device_code: str
    expires_in: int
    interval: int
    message: str


class TokenRequest(BaseModel):
    device_code: str


class TokenResponse(BaseModel):
    status: str  # "pending" | "success" | "expired" | "error"
    access_token: str | None = None
    error: str | None = None


@router.post("/auth/device-code", response_model=DeviceCodeResponse)
async def initiate_device_code():
    """Start a device code flow — returns a code the user enters at Microsoft's login page."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            DEVICE_CODE_URL,
            data={
                "client_id": AZURE_CLIENT_ID,
                "scope": AZURE_MANAGEMENT_SCOPE,
            },
            timeout=15.0,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Azure error: {resp.text}")
        data = resp.json()
        return DeviceCodeResponse(
            user_code=data["user_code"],
            verification_uri=data["verification_uri"],
            device_code=data["device_code"],
            expires_in=data["expires_in"],
            interval=data.get("interval", 5),
            message=data["message"],
        )


@router.post("/auth/device-code/token", response_model=TokenResponse)
async def poll_device_code_token(body: TokenRequest):
    """Poll for token after user completes device code sign-in."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": AZURE_CLIENT_ID,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": body.device_code,
            },
            timeout=15.0,
        )
        data = resp.json()

        if resp.status_code == 200:
            return TokenResponse(
                status="success",
                access_token=data.get("access_token"),
            )

        error = data.get("error", "")
        if error == "authorization_pending":
            return TokenResponse(status="pending")
        elif error == "expired_token":
            return TokenResponse(status="expired", error="Sign-in code expired. Please try again.")
        elif error == "authorization_declined":
            return TokenResponse(status="error", error="Sign-in was declined.")
        else:
            return TokenResponse(
                status="error",
                error=data.get("error_description", "Authentication failed"),
            )
