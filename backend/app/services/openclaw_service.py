"""OpenClaw lifecycle service — deploy, update, delete OpenClawInstance CRs per agent.

Secrets are NEVER stored in YAML or base64.  All sensitive values (API keys,
bot tokens) live in Azure Key Vault and are mounted via CSI SecretProviderClass.
"""

import asyncio
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Azure infrastructure references
KEY_VAULT_NAME = os.getenv("KEY_VAULT_NAME", "stumsft-aiplat-prod-kv")
TENANT_ID = os.getenv("AZURE_TENANT_ID", "9dce4dc6-16c7-48c4-9f57-52897cc5a893")
WORKLOAD_CLIENT_ID = os.getenv(
    "AZURE_WORKLOAD_CLIENT_ID",
    os.getenv("AZURE_CLIENT_ID", "0a33a4b9-824c-4ed4-9f4c-615ea40bd502"),
)

# OpenClaw CRD coordinates
OPENCLAW_GROUP = "openclaw.rocks"
OPENCLAW_VERSION = "v1alpha1"
OPENCLAW_PLURAL = "openclawinstances"


def _sanitize_name(name: str) -> str:
    """Convert an agent name to a valid K8s resource name."""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9-]", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:63] or "agent"


def _get_k8s_clients():
    from kubernetes import client, config

    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.CoreV1Api(), client.CustomObjectsApi()


class OpenClawService:
    """Manages OpenClaw agent instances as K8s Custom Resources.

    Each OpenClaw agent gets:
    1.  A CSI SecretProviderClass → pulls secrets from Key Vault
    2.  An OpenClawInstance CR     → operator creates the StatefulSet
    """

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    async def deploy_agent(
        self,
        agent_id: str,
        agent_name: str,
        tenant_slug: str,
        system_prompt: str,
        model_endpoint: Optional[dict],
        openclaw_config: Optional[dict],
    ) -> str:
        """Deploy an OpenClawInstance for the given agent.  Returns the instance name."""
        instance_name = f"oc-{_sanitize_name(agent_name)}-{agent_id[:8]}"
        namespace = f"tenant-{tenant_slug}"

        # Resolve model from the platform's model endpoint
        model_id, base_url = self._resolve_model(model_endpoint)

        # Build the CR body
        cr = self._build_cr(
            instance_name=instance_name,
            namespace=namespace,
            agent_id=agent_id,
            system_prompt=system_prompt or "You are a helpful assistant.",
            model_id=model_id,
            base_url=base_url,
            openclaw_config=openclaw_config or {},
        )

        # Build the CSI SecretProviderClass for this agent
        spc = self._build_secret_provider_class(
            instance_name=instance_name,
            namespace=namespace,
            openclaw_config=openclaw_config or {},
        )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._apply_resources, namespace, instance_name, spc, cr)

        logger.info(
            "Deployed OpenClaw instance %s in %s for agent %s",
            instance_name, namespace, agent_id,
        )
        return instance_name

    async def update_agent(
        self,
        instance_name: str,
        tenant_slug: str,
        system_prompt: str,
        model_endpoint: Optional[dict],
        openclaw_config: Optional[dict],
    ) -> None:
        """Update an existing OpenClawInstance CR."""
        namespace = f"tenant-{tenant_slug}"
        model_id, base_url = self._resolve_model(model_endpoint)

        cr = self._build_cr(
            instance_name=instance_name,
            namespace=namespace,
            agent_id="",
            system_prompt=system_prompt or "You are a helpful assistant.",
            model_id=model_id,
            base_url=base_url,
            openclaw_config=openclaw_config or {},
        )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._replace_cr, namespace, instance_name, cr)

        logger.info("Updated OpenClaw instance %s in %s", instance_name, namespace)

    async def delete_agent(self, instance_name: str, tenant_slug: str) -> None:
        """Delete an OpenClawInstance CR and its SecretProviderClass."""
        namespace = f"tenant-{tenant_slug}"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._delete_resources, namespace, instance_name)
        logger.info("Deleted OpenClaw instance %s in %s", instance_name, namespace)

    # ------------------------------------------------------------------ #
    #  Model resolution
    # ------------------------------------------------------------------ #

    @staticmethod
    def _resolve_model(endpoint: Optional[dict]) -> tuple[str, str]:
        """Map a platform ModelEndpoint to OpenClaw provider/model + base URL."""
        if not endpoint:
            return "azure-openai-responses/gpt-4.1", ""

        provider = (endpoint.get("provider_type") or "").lower()
        model = endpoint.get("model_name", "gpt-4.1")
        api_base = endpoint.get("api_base", "")

        if "azure" in provider:
            # Azure OpenAI — use the azure-openai-responses provider
            base_url = api_base.rstrip("/")
            if not base_url.endswith("/openai/v1"):
                base_url = f"{base_url}/openai/v1"
            return f"azure-openai-responses/{model}", base_url
        else:
            return f"openai/{model}", api_base

    # ------------------------------------------------------------------ #
    #  CR builders (zero secrets in YAML)
    # ------------------------------------------------------------------ #

    def _build_cr(
        self,
        instance_name: str,
        namespace: str,
        agent_id: str,
        system_prompt: str,
        model_id: str,
        base_url: str,
        openclaw_config: dict,
    ) -> dict:
        """Build the OpenClawInstance CR body."""
        provider_name = model_id.split("/")[0] if "/" in model_id else "azure-openai-responses"
        model_name = model_id.split("/")[-1]

        # Channels
        channels_config: dict = {}
        channels = openclaw_config.get("channels") or {}
        if channels.get("telegram_enabled"):
            channels_config["telegram"] = {
                "enabled": True,
                "dmPolicy": channels.get("dm_policy", "allowlist"),
            }
            allowed = channels.get("telegram_allowed_users", [])
            if allowed:
                channels_config["telegram"]["allowFrom"] = [str(u) for u in allowed]
            else:
                # Use Key Vault default — value is injected via CSI env var
                channels_config["telegram"]["allowFrom"] = ["${TELEGRAM_ALLOW_FROM}"]

        # MCP servers
        mcp_servers: dict = {}
        for url in openclaw_config.get("mcp_server_urls", []):
            # Derive name from URL
            name = url.rstrip("/").split("/")[-1].split(".")[0].replace("mcp-", "")
            mcp_servers[name] = {"url": url}

        # Model provider config — API key injected via env var from CSI, never in YAML
        providers_config = {
            provider_name: {
                "apiKey": "${AZURE_API_KEY}",
                "api": "openai-responses",
                "authHeader": False,
                "headers": {"api-key": "${AZURE_API_KEY}"},
                "models": [
                    {
                        "id": model_name,
                        "name": f"{model_name} (Azure)",
                        "reasoning": model_name in ("gpt-5.4", "gpt-5.2", "gpt-5.2-codex"),
                        "input": ["text", "image"],
                        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                        "contextWindow": 400000 if "5" in model_name else 1047576,
                        "maxTokens": 16384,
                        "compat": {"supportsStore": False},
                    }
                ],
            }
        }
        if base_url:
            providers_config[provider_name]["baseUrl"] = base_url

        # If deep research is enabled, add gpt-5.4 as a secondary model
        if openclaw_config.get("enable_deep_research") and "5.4" not in model_name:
            providers_config[provider_name]["models"].append({
                "id": "gpt-5.4",
                "name": "GPT-5.4 (Azure, Deep Research)",
                "reasoning": True,
                "input": ["text", "image"],
                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                "contextWindow": 400000,
                "maxTokens": 16384,
                "compat": {"supportsStore": False},
            })

        raw_config: dict = {
            "models": {"providers": providers_config},
            "agents": {
                "defaults": {
                    "model": {"primary": model_id},
                    "systemPrompt": system_prompt,
                }
            },
            "session": {"scope": "per-sender"},
        }

        if channels_config:
            raw_config["channels"] = channels_config
        if mcp_servers:
            raw_config["agents"]["defaults"]["mcpServers"] = mcp_servers

        # Deep research — allow agent to upgrade to gpt-5.4 for complex tasks
        if openclaw_config.get("enable_deep_research") and "5.4" not in model_name:
            raw_config["agents"]["defaults"]["model"]["research"] = f"{provider_name}/gpt-5.4"

        cr = {
            "apiVersion": f"{OPENCLAW_GROUP}/{OPENCLAW_VERSION}",
            "kind": "OpenClawInstance",
            "metadata": {
                "name": instance_name,
                "namespace": namespace,
                "labels": {
                    "app.kubernetes.io/part-of": "aiplatform",
                    "aiplatform/agent-id": agent_id[:63] if agent_id else "",
                    "aiplatform/agent-type": "openclaw",
                },
            },
            "spec": {
                "envFrom": [{"secretRef": {"name": f"{instance_name}-secrets"}}],
                "storage": {"persistence": {"enabled": True, "size": "10Gi"}},
                "config": {"raw": raw_config},
            },
        }

        # Optional features
        if openclaw_config.get("enable_web_browsing", True):
            cr["spec"]["chromium"] = {
                "enabled": True,
                "persistence": {"enabled": True, "size": "1Gi"},
            }

        return cr

    def _build_secret_provider_class(
        self, instance_name: str, namespace: str, openclaw_config: dict
    ) -> dict:
        """Build CSI SecretProviderClass that pulls secrets from Key Vault.

        The actual secret values live ONLY in Key Vault — they are projected
        into the pod as env vars via the CSI driver, never stored in K8s
        Secrets or YAML.
        """
        # Secrets to pull from Key Vault
        kv_objects = [
            {"objectName": "azure-openai-api-key", "objectType": "secret", "objectAlias": "AZURE_API_KEY"},
        ]

        channels = openclaw_config.get("channels") or {}
        if channels.get("telegram_enabled"):
            token_secret = channels.get("telegram_bot_token_secret", "TELEGRAMBOTTOKEN")
            kv_objects.append(
                {"objectName": token_secret, "objectType": "secret", "objectAlias": "TELEGRAM_BOT_TOKEN"}
            )
            # Also pull allowed-from list if user didn't provide explicit IDs
            allowed = channels.get("telegram_allowed_users", [])
            if not allowed:
                kv_objects.append(
                    {"objectName": "TELEGRAMALLOWFROM", "objectType": "secret", "objectAlias": "TELEGRAM_ALLOW_FROM"}
                )

        # Build the objects YAML string for CSI
        import json
        objects_str = json.dumps({"array": kv_objects})

        spc = {
            "apiVersion": "secrets-store.csi.x-k8s.io/v1",
            "kind": "SecretProviderClass",
            "metadata": {
                "name": f"{instance_name}-secrets-provider",
                "namespace": namespace,
            },
            "spec": {
                "provider": "azure",
                "parameters": {
                    "usePodIdentity": "false",
                    "useVMManagedIdentity": "false",
                    "clientID": WORKLOAD_CLIENT_ID,
                    "keyvaultName": KEY_VAULT_NAME,
                    "tenantId": TENANT_ID,
                    "objects": objects_str,
                },
                "secretObjects": [
                    {
                        "secretName": f"{instance_name}-secrets",
                        "type": "Opaque",
                        "data": [
                            {"objectName": obj["objectAlias"], "key": obj["objectAlias"]}
                            for obj in kv_objects
                        ],
                    }
                ],
            },
        }
        return spc

    # ------------------------------------------------------------------ #
    #  K8s operations (run in thread pool)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _apply_resources(namespace: str, instance_name: str, spc: dict, cr: dict) -> None:
        """Create or update CSI SecretProviderClass + OpenClawInstance CR."""
        from kubernetes import client

        core_v1, custom_api = _get_k8s_clients()

        # 1. Apply SecretProviderClass
        try:
            custom_api.create_namespaced_custom_object(
                group="secrets-store.csi.x-k8s.io",
                version="v1",
                namespace=namespace,
                plural="secretproviderclasses",
                body=spc,
            )
            logger.info("Created SecretProviderClass %s-secrets-provider", instance_name)
        except client.ApiException as e:
            if e.status == 409:
                custom_api.patch_namespaced_custom_object(
                    group="secrets-store.csi.x-k8s.io",
                    version="v1",
                    namespace=namespace,
                    plural="secretproviderclasses",
                    name=f"{instance_name}-secrets-provider",
                    body=spc,
                )
                logger.info("Updated SecretProviderClass %s-secrets-provider", instance_name)
            else:
                raise

        # 2. Apply OpenClawInstance CR
        try:
            custom_api.create_namespaced_custom_object(
                group=OPENCLAW_GROUP,
                version=OPENCLAW_VERSION,
                namespace=namespace,
                plural=OPENCLAW_PLURAL,
                body=cr,
            )
            logger.info("Created OpenClawInstance %s", instance_name)
        except client.ApiException as e:
            if e.status == 409:
                custom_api.patch_namespaced_custom_object(
                    group=OPENCLAW_GROUP,
                    version=OPENCLAW_VERSION,
                    namespace=namespace,
                    plural=OPENCLAW_PLURAL,
                    name=instance_name,
                    body=cr,
                )
                logger.info("Updated OpenClawInstance %s", instance_name)
            else:
                raise

    @staticmethod
    def _replace_cr(namespace: str, instance_name: str, cr: dict) -> None:
        """Patch an existing OpenClawInstance CR (for updates)."""
        from kubernetes import client

        _, custom_api = _get_k8s_clients()
        try:
            custom_api.patch_namespaced_custom_object(
                group=OPENCLAW_GROUP,
                version=OPENCLAW_VERSION,
                namespace=namespace,
                plural=OPENCLAW_PLURAL,
                name=instance_name,
                body=cr,
            )
        except client.ApiException as e:
            if e.status == 404:
                logger.warning("OpenClawInstance %s not found — creating", instance_name)
                custom_api.create_namespaced_custom_object(
                    group=OPENCLAW_GROUP,
                    version=OPENCLAW_VERSION,
                    namespace=namespace,
                    plural=OPENCLAW_PLURAL,
                    body=cr,
                )
            else:
                raise

    @staticmethod
    def _delete_resources(namespace: str, instance_name: str) -> None:
        """Delete OpenClawInstance CR and SecretProviderClass."""
        from kubernetes import client

        _, custom_api = _get_k8s_clients()

        # Delete CR
        try:
            custom_api.delete_namespaced_custom_object(
                group=OPENCLAW_GROUP,
                version=OPENCLAW_VERSION,
                namespace=namespace,
                plural=OPENCLAW_PLURAL,
                name=instance_name,
            )
            logger.info("Deleted OpenClawInstance %s", instance_name)
        except client.ApiException as e:
            if e.status != 404:
                raise

        # Delete SecretProviderClass
        try:
            custom_api.delete_namespaced_custom_object(
                group="secrets-store.csi.x-k8s.io",
                version="v1",
                namespace=namespace,
                plural="secretproviderclasses",
                name=f"{instance_name}-secrets-provider",
            )
            logger.info("Deleted SecretProviderClass %s-secrets-provider", instance_name)
        except client.ApiException as e:
            if e.status != 404:
                raise
