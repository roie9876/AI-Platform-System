import httpx
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AzureARMService:
    """Service for interacting with Azure Resource Manager APIs."""

    ARM_BASE = "https://management.azure.com"

    async def list_subscriptions(self, access_token: str) -> list[dict]:
        """List Azure subscriptions accessible with the given token."""
        url = f"{self.ARM_BASE}/subscriptions"
        params = {"api-version": "2022-12-01"}
        results = []

        async with httpx.AsyncClient() as client:
            while url:
                resp = await client.get(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )
                resp.raise_for_status()
                data = resp.json()
                for sub in data.get("value", []):
                    results.append({
                        "subscriptionId": sub.get("subscriptionId"),
                        "displayName": sub.get("displayName"),
                        "tenantId": sub.get("tenantId"),
                        "state": sub.get("state"),
                    })
                url = data.get("nextLink")
                params = None  # nextLink already includes query params

        return results

    async def list_resources_by_type(
        self, access_token: str, subscription_id: str, resource_type: str
    ) -> list[dict]:
        """List Azure resources of a specific type within a subscription."""
        url = f"{self.ARM_BASE}/subscriptions/{subscription_id}/resources"
        params = {
            "$filter": f"resourceType eq '{resource_type}'",
            "api-version": "2021-04-01",
        }
        results = []

        async with httpx.AsyncClient() as client:
            while url:
                try:
                    resp = await client.get(
                        url,
                        params=params,
                        headers={"Authorization": f"Bearer {access_token}"},
                        timeout=30.0,
                    )
                    if resp.status_code in (401, 403, 404):
                        return []
                    resp.raise_for_status()
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (401, 403, 404):
                        return []
                    raise

                data = resp.json()
                for resource in data.get("value", []):
                    resource_id = resource.get("id", "")
                    parts = resource_id.split("/")
                    rg_name = None
                    for i, part in enumerate(parts):
                        if part.lower() == "resourcegroups" and i + 1 < len(parts):
                            rg_name = parts[i + 1]
                            break

                    results.append({
                        "id": resource_id,
                        "name": resource.get("name"),
                        "type": resource.get("type"),
                        "location": resource.get("location"),
                        "resourceGroup": rg_name,
                    })
                url = data.get("nextLink")
                params = None

        return results

    async def _get_search_admin_key(
        self, access_token: str, resource_id: str
    ) -> str | None:
        """Get admin key for an Azure AI Search service via ARM API."""
        url = f"{self.ARM_BASE}{resource_id}/listAdminKeys"
        params = {"api-version": "2023-11-01"}

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    url,
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                    timeout=30.0,
                )
                logger.info("listAdminKeys status: %s", resp.status_code)
                if resp.status_code in (403, 404):
                    logger.warning("listAdminKeys denied: %s %s", resp.status_code, resp.text[:200])
                    return None
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error("listAdminKeys error: %s %s", e.response.status_code, e.response.text[:200])
                return None

            data = resp.json()
            return data.get("primaryKey")

    def _extract_search_service_name(self, resource_id: str) -> str | None:
        """Extract the search service name from an ARM resource ID."""
        parts = resource_id.rstrip("/").split("/")
        return parts[-1] if parts else None

    async def list_search_indexes(
        self, access_token: str, resource_id: str
    ) -> list[dict]:
        """List indexes in an Azure AI Search service using the data plane API."""
        service_name = self._extract_search_service_name(resource_id)
        if not service_name:
            return []

        admin_key = await self._get_search_admin_key(access_token, resource_id)
        if not admin_key:
            return []

        url = f"https://{service_name}.search.windows.net/indexes"
        params = {"api-version": "2024-07-01", "$select": "name"}

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    url,
                    params=params,
                    headers={"api-key": admin_key},
                    timeout=30.0,
                )
                if resp.status_code in (403, 404):
                    return []
                resp.raise_for_status()
            except httpx.HTTPStatusError:
                return []

            data = resp.json()
            return [{"name": idx.get("name")} for idx in data.get("value", [])]
