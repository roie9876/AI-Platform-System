"""Microsoft Entra ID group management via Microsoft Graph API."""

from __future__ import annotations

import logging
import os

import httpx
from azure.identity import ClientSecretCredential, DefaultAzureCredential

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _get_credential():
    """Get credential for Microsoft Graph API calls.

    Prefers explicit client secret (ENTRA_CLIENT_SECRET) for the app registration.
    Falls back to DefaultAzureCredential (managed identity / workload identity).
    """
    tenant_id = os.getenv("AZURE_TENANT_ID", "")
    client_id = os.getenv("ENTRA_APP_CLIENT_ID", "") or os.getenv("AZURE_CLIENT_ID", "")
    client_secret = os.getenv("ENTRA_CLIENT_SECRET", "")

    if client_secret and tenant_id and client_id:
        return ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
    # Fall back to workload identity / managed identity
    return DefaultAzureCredential()


def _get_token() -> str:
    """Get an access token for Microsoft Graph."""
    credential = _get_credential()
    token = credential.get_token("https://graph.microsoft.com/.default")
    return token.token


class EntraGroupService:
    """Create and delete Entra ID security groups via Microsoft Graph."""

    async def create_group(self, tenant_name: str, tenant_slug: str) -> str | None:
        """Create a security group for a tenant. Returns the group Object ID."""
        display_name = f"AI Platform - {tenant_name} Users"
        mail_nickname = f"aiplatform-{tenant_slug}"

        body = {
            "displayName": display_name,
            "mailNickname": mail_nickname,
            "mailEnabled": False,
            "securityEnabled": True,
            "description": f"Users with access to the '{tenant_name}' tenant on AI Agent Platform",
        }

        try:
            token = _get_token()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{GRAPH_BASE}/groups",
                    json=body,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    timeout=30,
                )

            if resp.status_code == 201:
                group_id = resp.json()["id"]
                logger.info(
                    "Created Entra group '%s' (id=%s) for tenant '%s'",
                    display_name, group_id, tenant_slug,
                )
                return group_id

            logger.error(
                "Failed to create Entra group: %s %s", resp.status_code, resp.text
            )
            return None

        except Exception:
            logger.exception("Error creating Entra group for tenant '%s'", tenant_slug)
            return None

    async def add_member(self, group_id: str, user_email: str) -> bool:
        """Add a user to an Entra group by email (UPN lookup)."""
        try:
            token = _get_token()
            async with httpx.AsyncClient() as client:
                # Look up user by email / UPN
                user_resp = await client.get(
                    f"{GRAPH_BASE}/users/{user_email}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=15,
                )
                if user_resp.status_code != 200:
                    logger.warning("User '%s' not found in Entra: %s", user_email, user_resp.status_code)
                    return False

                user_id = user_resp.json()["id"]

                # Add to group
                member_resp = await client.post(
                    f"{GRAPH_BASE}/groups/{group_id}/members/$ref",
                    json={"@odata.id": f"{GRAPH_BASE}/directoryObjects/{user_id}"},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    timeout=15,
                )

            if member_resp.status_code in (204, 200):
                logger.info("Added user '%s' to Entra group %s", user_email, group_id)
                return True

            if member_resp.status_code == 400 and "already exist" in member_resp.text.lower():
                logger.info("User '%s' already in group %s", user_email, group_id)
                return True

            logger.warning(
                "Failed to add user to group: %s %s", member_resp.status_code, member_resp.text
            )
            return False

        except Exception:
            logger.exception("Error adding user '%s' to group %s", user_email, group_id)
            return False

    async def delete_group(self, group_id: str) -> bool:
        """Delete an Entra group by Object ID."""
        if not group_id:
            return True

        try:
            token = _get_token()
            async with httpx.AsyncClient() as client:
                resp = await client.delete(
                    f"{GRAPH_BASE}/groups/{group_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=15,
                )

            if resp.status_code in (204, 404):
                logger.info("Deleted Entra group %s", group_id)
                return True

            logger.error("Failed to delete Entra group %s: %s %s", group_id, resp.status_code, resp.text)
            return False

        except Exception:
            logger.exception("Error deleting Entra group %s", group_id)
            return False
