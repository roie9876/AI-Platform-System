import asyncio
import logging
import os
import tempfile
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.repositories.tool_repo import ToolRepository

logger = logging.getLogger(__name__)


class PlatformToolAdapter(ABC):
    """Base class for all platform AI service tools."""

    @abstractmethod
    def service_name(self) -> str:
        """Return the Azure AI service name."""

    @abstractmethod
    def tool_name(self) -> str:
        """Return the tool name for registration."""

    @abstractmethod
    def description(self) -> str:
        """Return human-readable description."""

    @abstractmethod
    def get_input_schema(self) -> dict:
        """Return JSON Schema for this tool's input."""

    @abstractmethod
    async def execute(self, input_data: dict) -> dict:
        """Execute the AI service call and return result."""


class AzureAISearchAdapter(PlatformToolAdapter):
    """Azure AI Search — search indexed documents."""

    def service_name(self) -> str:
        return "Azure AI Search"

    def tool_name(self) -> str:
        return "azure_ai_search"

    def description(self) -> str:
        return "Search indexed documents using Azure AI Search with hybrid vector + keyword search."

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query text"},
                "top_k": {"type": "integer", "description": "Number of results to return", "default": 5},
                "index_name": {"type": "string", "description": "Name of the search index"},
            },
            "required": ["query", "index_name"],
        }

    async def execute(self, input_data: dict) -> dict:
        endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
        api_key = os.environ.get("AZURE_SEARCH_API_KEY")

        if not endpoint:
            return {
                "status": "not_configured",
                "message": "Azure AI Search not configured. Set AZURE_SEARCH_ENDPOINT and AZURE_SEARCH_API_KEY environment variables.",
            }

        try:
            from azure.core.credentials import AzureKeyCredential
            from azure.search.documents import SearchClient

            client = SearchClient(
                endpoint=endpoint,
                index_name=input_data["index_name"],
                credential=AzureKeyCredential(api_key) if api_key else None,
            )
            results = client.search(
                search_text=input_data["query"],
                top=input_data.get("top_k", 5),
            )
            docs = [{"score": r["@search.score"], "content": r.get("content", "")} for r in results]
            return {"status": "success", "results": docs, "count": len(docs)}
        except ImportError:
            return {"status": "sdk_not_installed", "message": "azure-search-documents package not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class ContentSafetyAdapter(PlatformToolAdapter):
    """Azure AI Content Safety — analyze text for harmful content."""

    def service_name(self) -> str:
        return "Azure AI Content Safety"

    def tool_name(self) -> str:
        return "azure_content_safety"

    def description(self) -> str:
        return "Analyze text for harmful content (hate, violence, self-harm, sexual) using Azure AI Content Safety."

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to analyze for content safety"},
            },
            "required": ["text"],
        }

    async def execute(self, input_data: dict) -> dict:
        endpoint = os.environ.get("AZURE_CONTENT_SAFETY_ENDPOINT")
        api_key = os.environ.get("AZURE_CONTENT_SAFETY_API_KEY")

        if not endpoint:
            return {
                "status": "not_configured",
                "message": "Azure Content Safety not configured. Set AZURE_CONTENT_SAFETY_ENDPOINT and AZURE_CONTENT_SAFETY_API_KEY.",
            }

        try:
            from azure.ai.contentsafety import ContentSafetyClient
            from azure.ai.contentsafety.models import AnalyzeTextOptions
            from azure.core.credentials import AzureKeyCredential

            client = ContentSafetyClient(endpoint, AzureKeyCredential(api_key))
            response = client.analyze_text(AnalyzeTextOptions(text=input_data["text"]))
            categories = {cat.category: cat.severity for cat in response.categories_analysis}
            return {"status": "success", "categories": categories}
        except ImportError:
            return {"status": "sdk_not_installed", "message": "azure-ai-contentsafety package not installed"}
        except Exception as e:
            return {"status": "error", "message": str(e)}


class DocumentIntelligenceAdapter(PlatformToolAdapter):
    """Azure AI Document Intelligence — extract text and structure from documents."""

    def service_name(self) -> str:
        return "Azure AI Document Intelligence"

    def tool_name(self) -> str:
        return "azure_document_intelligence"

    def description(self) -> str:
        return "Extract text, tables, and key-value pairs from documents using Azure AI Document Intelligence."

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "document_url": {"type": "string", "description": "URL of the document to analyze"},
                "model_id": {
                    "type": "string",
                    "description": "Model to use (prebuilt-read, prebuilt-layout, etc.)",
                    "default": "prebuilt-read",
                },
            },
            "required": ["document_url"],
        }

    async def execute(self, input_data: dict) -> dict:
        return {
            "status": "stub",
            "message": "Document Intelligence adapter — implement with azure-ai-documentintelligence SDK for production",
            "input": input_data,
        }


class LanguageAdapter(PlatformToolAdapter):
    """Azure AI Language — sentiment analysis, NER, summarization."""

    def service_name(self) -> str:
        return "Azure AI Language"

    def tool_name(self) -> str:
        return "azure_language"

    def description(self) -> str:
        return "Analyze text for sentiment, named entities, and summarization using Azure AI Language."

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to analyze"},
                "operation": {
                    "type": "string",
                    "enum": ["sentiment", "entities", "summarize"],
                    "description": "Analysis operation to perform",
                },
            },
            "required": ["text", "operation"],
        }

    async def execute(self, input_data: dict) -> dict:
        return {
            "status": "stub",
            "message": "Language adapter — implement with azure-ai-textanalytics SDK for production",
            "input": input_data,
        }


class TranslationAdapter(PlatformToolAdapter):
    """Azure AI Translation — translate text between languages."""

    def service_name(self) -> str:
        return "Azure AI Translation"

    def tool_name(self) -> str:
        return "azure_translation"

    def description(self) -> str:
        return "Translate text between languages using Azure AI Translation."

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to translate"},
                "target_language": {"type": "string", "description": "Target language code (e.g., 'en', 'es', 'fr')"},
                "source_language": {"type": "string", "description": "Source language code (auto-detected if not provided)"},
            },
            "required": ["text", "target_language"],
        }

    async def execute(self, input_data: dict) -> dict:
        return {
            "status": "stub",
            "message": "Translation adapter — implement with Azure Translator REST API for production",
            "input": input_data,
        }


class SpeechAdapter(PlatformToolAdapter):
    """Azure AI Speech — speech-to-text and text-to-speech."""

    def service_name(self) -> str:
        return "Azure AI Speech"

    def tool_name(self) -> str:
        return "azure_speech"

    def description(self) -> str:
        return "Convert speech to text or text to speech using Azure AI Speech."

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to synthesize to speech"},
                "operation": {
                    "type": "string",
                    "enum": ["tts", "stt"],
                    "description": "Operation: tts (text-to-speech) or stt (speech-to-text)",
                },
            },
            "required": ["operation"],
        }

    async def execute(self, input_data: dict) -> dict:
        return {
            "status": "stub",
            "message": "Speech adapter — implement with azure-cognitiveservices-speech SDK for production",
            "input": input_data,
        }


class VisionAdapter(PlatformToolAdapter):
    """Azure AI Vision — image analysis."""

    def service_name(self) -> str:
        return "Azure AI Vision"

    def tool_name(self) -> str:
        return "azure_vision"

    def description(self) -> str:
        return "Analyze images for objects, text, and visual features using Azure AI Vision."

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "image_url": {"type": "string", "description": "URL of the image to analyze"},
                "features": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Features to extract (caption, tags, objects, read)",
                },
            },
            "required": ["image_url"],
        }

    async def execute(self, input_data: dict) -> dict:
        return {
            "status": "stub",
            "message": "Vision adapter — implement with azure-ai-vision-imageanalysis SDK for production",
            "input": input_data,
        }


class CodeInterpreterAdapter(PlatformToolAdapter):
    """Code Interpreter — execute Python code in a sandboxed subprocess."""

    MAX_OUTPUT = 65536  # 64 KB
    TIMEOUT = 30  # seconds

    def service_name(self) -> str:
        return "Code Interpreter"

    def tool_name(self) -> str:
        return "code_interpreter"

    def description(self) -> str:
        return "Execute Python code and return stdout, stderr, and exit code."

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
            },
            "required": ["code"],
        }

    async def execute(self, input_data: dict) -> dict:
        code = input_data.get("code", "")
        if not code.strip():
            return {"status": "error", "message": "No code provided"}

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False
            ) as f:
                f.write(code)
                script_path = f.name

            process = await asyncio.create_subprocess_exec(
                "python3", script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=self.TIMEOUT
                )
            except asyncio.TimeoutError:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
                return {
                    "status": "error",
                    "message": f"Code execution timed out after {self.TIMEOUT}s",
                }
            finally:
                try:
                    os.unlink(script_path)
                except OSError:
                    pass

            stdout_text = stdout_bytes.decode("utf-8", errors="replace")[: self.MAX_OUTPUT]
            stderr_text = stderr_bytes.decode("utf-8", errors="replace")[: self.MAX_OUTPUT]

            return {
                "status": "success" if process.returncode == 0 else "error",
                "stdout": stdout_text,
                "stderr": stderr_text,
                "exit_code": process.returncode,
            }
        except Exception as e:
            logger.exception("Code interpreter execution failed")
            return {"status": "error", "message": str(e)}


# Registry of all platform tool adapters
PLATFORM_ADAPTERS: List[PlatformToolAdapter] = [
    AzureAISearchAdapter(),
    ContentSafetyAdapter(),
    DocumentIntelligenceAdapter(),
    LanguageAdapter(),
    TranslationAdapter(),
    SpeechAdapter(),
    VisionAdapter(),
    CodeInterpreterAdapter(),
]


_tool_repo = ToolRepository()


async def register_platform_tools(tenant_id: str) -> list[dict]:
    """Register all platform tool adapters as Tool records (is_platform_tool=True).
    Idempotent — skips tools that already exist by name."""
    registered = []
    for adapter in PLATFORM_ADAPTERS:
        existing = await _tool_repo.query(
            tenant_id,
            "SELECT * FROM c WHERE c.name = @name AND c.is_platform_tool = true",
            [{"name": "@name", "value": adapter.tool_name()}],
        )
        if existing:
            registered.append(existing[0])
            continue

        tool = {
            "id": str(uuid4()),
            "name": adapter.tool_name(),
            "description": adapter.description(),
            "input_schema": adapter.get_input_schema(),
            "is_platform_tool": True,
            "tenant_id": tenant_id,
            "timeout_seconds": 30,
        }
        created = await _tool_repo.create(tenant_id, tool)
        registered.append(created)

    return registered


def get_adapter_by_name(tool_name: str) -> Optional[PlatformToolAdapter]:
    """Look up a platform tool adapter by tool name."""
    for adapter in PLATFORM_ADAPTERS:
        if adapter.tool_name() == tool_name:
            return adapter
    return None
