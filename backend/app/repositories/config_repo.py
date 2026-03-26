"""ModelEndpoint, ModelPricing, CostAlert, AzureSubscription, AzureConnection, and CatalogEntry repositories."""

from app.repositories.base import CosmosRepository


class ModelEndpointRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("model_endpoints")

    async def list_by_tenant(self, tenant_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid",
            [{"name": "@tid", "value": tenant_id}],
        )


class ModelPricingRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("model_pricing")


class CostAlertRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("cost_alerts")

    async def list_by_tenant(self, tenant_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid",
            [{"name": "@tid", "value": tenant_id}],
        )


class AzureSubscriptionRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("azure_subscriptions")


class AzureConnectionRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("azure_connections")

    async def list_by_agent(self, tenant_id: str, agent_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid",
            [{"name": "@tid", "value": tenant_id}, {"name": "@aid", "value": agent_id}],
        )


class CatalogEntryRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("catalog_entries")

    async def list_by_tenant(self, tenant_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid",
            [{"name": "@tid", "value": tenant_id}],
        )
