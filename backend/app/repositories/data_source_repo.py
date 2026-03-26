"""DataSource, Document, and DocumentChunk repositories for Cosmos DB."""

from app.repositories.base import CosmosRepository


class DataSourceRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("data_sources")

    async def list_by_agent(self, tenant_id: str, agent_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid",
            [{"name": "@tid", "value": tenant_id}, {"name": "@aid", "value": agent_id}],
        )


class AgentDataSourceRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("agent_data_sources")


class DocumentRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("documents")

    async def list_by_data_source(self, tenant_id: str, data_source_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.data_source_id = @dsid",
            [{"name": "@tid", "value": tenant_id}, {"name": "@dsid", "value": data_source_id}],
        )


class DocumentChunkRepository(CosmosRepository):
    def __init__(self) -> None:
        super().__init__("document_chunks")

    async def list_by_document(self, tenant_id: str, document_id: str) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT * FROM c WHERE c.tenant_id = @tid AND c.document_id = @did",
            [{"name": "@tid", "value": tenant_id}, {"name": "@did", "value": document_id}],
        )

    async def search_by_embedding(self, tenant_id: str, agent_id: str, top_k: int = 10) -> list[dict]:
        return await self.query(
            tenant_id,
            "SELECT TOP @top_k * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid",
            [
                {"name": "@tid", "value": tenant_id},
                {"name": "@aid", "value": agent_id},
                {"name": "@top_k", "value": top_k},
            ],
        )
