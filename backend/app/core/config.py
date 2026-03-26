from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://aiplatform:devpassword@localhost:5432/aiplatform"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "change-me-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    ENVIRONMENT: str = "development"
    ENCRYPTION_KEY: str = "change-me-in-production-use-fernet-key"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Cosmos DB configuration
    COSMOS_ENDPOINT: str = ""
    COSMOS_DATABASE: str = "aiplatform"

    # Entra ID configuration
    AZURE_TENANT_ID: str = ""
    AZURE_CLIENT_ID: str = ""
    AZURE_AUTHORITY: str = ""
    AZURE_JWKS_URI: str = ""
    AZURE_ISSUER: str = ""

    # Workload Identity client ID (for Cosmos DB auth via DefaultAzureCredential)
    AZURE_WORKLOAD_CLIENT_ID: str = ""

    # Inter-service URLs (K8s DNS defaults)
    TOOL_EXECUTOR_URL: str = "http://tool-executor:8000"
    MCP_PROXY_URL: str = "http://mcp-proxy:8000"
    AGENT_EXECUTOR_URL: str = "http://agent-executor:8000"
    API_GATEWAY_URL: str = "http://api-gateway:8000"
    WORKFLOW_ENGINE_URL: str = "http://workflow-engine:8000"
    SERVICE_NAME: str = "monolith"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def model_post_init(self, __context: object) -> None:
        if self.AZURE_TENANT_ID:
            if not self.AZURE_AUTHORITY:
                self.AZURE_AUTHORITY = f"https://login.microsoftonline.com/{self.AZURE_TENANT_ID}"
            if not self.AZURE_JWKS_URI:
                self.AZURE_JWKS_URI = f"https://login.microsoftonline.com/{self.AZURE_TENANT_ID}/discovery/v2.0/keys"
            if not self.AZURE_ISSUER:
                self.AZURE_ISSUER = f"https://login.microsoftonline.com/{self.AZURE_TENANT_ID}/v2.0"


settings = Settings()
