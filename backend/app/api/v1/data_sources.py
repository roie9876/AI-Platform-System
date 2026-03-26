from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File

from app.middleware.tenant import get_tenant_id
from app.api.v1.dependencies import get_current_user
from app.repositories.agent_repo import AgentRepository
from app.repositories.data_source_repo import DataSourceRepository, AgentDataSourceRepository, DocumentRepository
from app.services.secret_store import encrypt_api_key
from app.services.rag_service import RAGService
from app.api.v1.schemas import (
    DataSourceCreateRequest,
    DataSourceUpdateRequest,
    DataSourceResponse,
    DataSourceListResponse,
    AgentDataSourceAttachRequest,
    AgentDataSourceResponse,
    DocumentResponse,
    DocumentListResponse,
    IngestURLRequest,
)

router = APIRouter()
agent_data_sources_router = APIRouter()

ds_repo = DataSourceRepository()
agent_ds_repo = AgentDataSourceRepository()
doc_repo = DocumentRepository()
agent_repo = AgentRepository()
_rag_service = RAGService()
ALLOWED_EXTENSIONS = {"pdf", "txt", "md", "docx"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("", response_model=DataSourceResponse, status_code=201)
async def create_data_source(
    body: DataSourceCreateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    if body.source_type not in ("file", "url"):
        raise HTTPException(status_code=400, detail="source_type must be 'file' or 'url'")

    credentials_encrypted = None
    if body.credentials:
        credentials_encrypted = encrypt_api_key(body.credentials)

    ds_data = {
        "name": body.name,
        "description": body.description,
        "source_type": body.source_type,
        "config": body.config,
        "credentials_encrypted": credentials_encrypted,
    }
    data_source = await ds_repo.create(tenant_id, ds_data)
    return data_source


@router.get("", response_model=DataSourceListResponse)
async def list_data_sources(
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    data_sources = await ds_repo.list_all(tenant_id)
    return DataSourceListResponse(data_sources=data_sources, total=len(data_sources))


@router.get("/{data_source_id}", response_model=DataSourceResponse)
async def get_data_source(
    data_source_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    data_source = await ds_repo.get(tenant_id, data_source_id)
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")
    return data_source


@router.put("/{data_source_id}", response_model=DataSourceResponse)
async def update_data_source(
    data_source_id: str,
    body: DataSourceUpdateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    data_source = await ds_repo.get(tenant_id, data_source_id)
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")

    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    data_source.update(update_data)
    updated = await ds_repo.update(tenant_id, data_source_id, data_source)
    return updated


@router.delete("/{data_source_id}", status_code=204)
async def delete_data_source(
    data_source_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    data_source = await ds_repo.get(tenant_id, data_source_id)
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")
    await ds_repo.delete(tenant_id, data_source_id)


# --- Document management endpoints ---


@router.post("/{data_source_id}/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(
    data_source_id: str,
    request: Request,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Upload and ingest a document into a data source."""
    data_source = await ds_repo.get(tenant_id, data_source_id)
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{ext}. Allowed: {ALLOWED_EXTENSIONS}",
        )

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    doc = await _rag_service.ingest_file(
        data_source_id=data_source_id,
        tenant_id=tenant_id,
        filename=file.filename,
        file_content=content,
    )
    return doc


@router.post("/{data_source_id}/ingest-url", response_model=DocumentResponse, status_code=201)
async def ingest_url(
    data_source_id: str,
    body: IngestURLRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """Ingest a URL's content into a data source."""
    data_source = await ds_repo.get(tenant_id, data_source_id)
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")

    try:
        doc = await _rag_service.ingest_url(
            data_source_id=data_source_id,
            tenant_id=tenant_id,
            url=body.url,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to ingest URL: {str(e)}")

    return doc


@router.get("/{data_source_id}/documents", response_model=DocumentListResponse)
async def list_documents(
    data_source_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """List all documents in a data source."""
    data_source = await ds_repo.get(tenant_id, data_source_id)
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")

    documents = await doc_repo.list_by_data_source(tenant_id, data_source_id)
    return DocumentListResponse(documents=documents, total=len(documents))


# --- Agent-DataSource attachment endpoints ---


@agent_data_sources_router.post(
    "/{agent_id}/data-sources", response_model=AgentDataSourceResponse, status_code=201
)
async def attach_data_source(
    agent_id: str,
    body: AgentDataSourceAttachRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    data_source = await ds_repo.get(tenant_id, str(body.data_source_id))
    if not data_source:
        raise HTTPException(status_code=404, detail="Data source not found")

    existing = await agent_ds_repo.query(
        tenant_id,
        "SELECT * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid AND c.data_source_id = @dsid",
        [
            {"name": "@tid", "value": tenant_id},
            {"name": "@aid", "value": agent_id},
            {"name": "@dsid", "value": str(body.data_source_id)},
        ],
    )
    if existing:
        raise HTTPException(status_code=409, detail="Data source already attached to agent")

    attachment_data = {"agent_id": agent_id, "data_source_id": str(body.data_source_id)}
    agent_ds = await agent_ds_repo.create(tenant_id, attachment_data)
    return agent_ds


@agent_data_sources_router.delete("/{agent_id}/data-sources/{data_source_id}", status_code=204)
async def detach_data_source(
    agent_id: str,
    data_source_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    existing = await agent_ds_repo.query(
        tenant_id,
        "SELECT * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid AND c.data_source_id = @dsid",
        [
            {"name": "@tid", "value": tenant_id},
            {"name": "@aid", "value": agent_id},
            {"name": "@dsid", "value": data_source_id},
        ],
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Data source not attached to agent")
    await agent_ds_repo.delete(tenant_id, existing[0]["id"])


@agent_data_sources_router.get(
    "/{agent_id}/data-sources", response_model=list[AgentDataSourceResponse]
)
async def list_agent_data_sources(
    agent_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    agent = await agent_repo.get(tenant_id, agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    attachments = await agent_ds_repo.query(
        tenant_id,
        "SELECT * FROM c WHERE c.tenant_id = @tid AND c.agent_id = @aid",
        [{"name": "@tid", "value": tenant_id}, {"name": "@aid", "value": agent_id}],
    )
    return attachments
