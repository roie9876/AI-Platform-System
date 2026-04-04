"""OpenClaw lifecycle service — deploy, update, delete OpenClawInstance CRs per agent.

Secrets are NEVER stored in YAML or base64.  All sensitive values (API keys,
bot tokens) live in Azure Key Vault and are mounted via CSI SecretProviderClass.
"""

import asyncio
import json
import logging
import os
import re
import uuid
from typing import Optional

logger = logging.getLogger(__name__)

# Azure infrastructure references (populated from K8s ConfigMap/Secrets at runtime)
KEY_VAULT_NAME = os.getenv("KEY_VAULT_NAME", "")
TENANT_KEY_VAULT_NAME = os.getenv("TENANT_KEY_VAULT_NAME", KEY_VAULT_NAME)
TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
WORKLOAD_CLIENT_ID = os.getenv(
    "AZURE_WORKLOAD_CLIENT_ID",
    os.getenv("AZURE_CLIENT_ID", ""),
)

# OpenClaw CRD coordinates
OPENCLAW_GROUP = "openclaw.rocks"
OPENCLAW_VERSION = "v1alpha1"
OPENCLAW_PLURAL = "openclawinstances"

# Custom OpenClaw image (patched for Baileys group-message fix)
OPENCLAW_IMAGE_REPO = os.getenv(
    "OPENCLAW_IMAGE_REPO", "stumsftaiplatformprodacr.azurecr.io/openclaw-patched"
)
OPENCLAW_IMAGE_TAG = os.getenv("OPENCLAW_IMAGE_TAG", "latest")


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

    def _get_kv_credential(self):
        """Get a credential for Key Vault using the workload identity.

        DefaultAzureCredential picks up AZURE_CLIENT_ID (the Entra app),
        but Key Vault access is granted to the managed identity
        (AZURE_WORKLOAD_CLIENT_ID).  We explicitly use that.
        """
        import os
        from azure.identity import WorkloadIdentityCredential, DefaultAzureCredential

        token_file = os.getenv("AZURE_FEDERATED_TOKEN_FILE")
        if token_file and WORKLOAD_CLIENT_ID:
            return WorkloadIdentityCredential(
                client_id=WORKLOAD_CLIENT_ID,
                tenant_id=TENANT_ID,
                token_file_path=token_file,
            )
        return DefaultAzureCredential()

    async def _get_kv_secret_as_list(self, secret_name: str) -> list[str]:
        """Fetch a Key Vault secret and split by comma/space into a list."""
        try:
            from azure.keyvault.secrets import SecretClient

            credential = self._get_kv_credential()
            kv_url = f"https://{KEY_VAULT_NAME}.vault.azure.net"
            secret_client = SecretClient(vault_url=kv_url, credential=credential)
            secret = secret_client.get_secret(secret_name)
            value = secret.value or ""
            items = [v.strip() for v in re.split(r"[,;\s]+", value) if v.strip()]
            return items
        except Exception as e:
            logger.warning("Could not fetch Key Vault secret %s: %s", secret_name, e)
            return []

    async def _get_kv_secret(self, secret_name: str) -> str:
        """Fetch a single Key Vault secret value."""
        try:
            from azure.keyvault.secrets import SecretClient

            credential = self._get_kv_credential()
            kv_url = f"https://{KEY_VAULT_NAME}.vault.azure.net"
            secret_client = SecretClient(vault_url=kv_url, credential=credential)
            secret = secret_client.get_secret(secret_name)
            return secret.value or ""
        except Exception as e:
            logger.warning("Could not fetch Key Vault secret %s: %s", secret_name, e)
            return ""

    async def _set_kv_secret(self, secret_name: str, secret_value: str) -> bool:
        """Store a secret in Key Vault. Returns True on success."""
        try:
            from azure.keyvault.secrets import SecretClient

            credential = self._get_kv_credential()
            kv_url = f"https://{KEY_VAULT_NAME}.vault.azure.net"
            secret_client = SecretClient(vault_url=kv_url, credential=credential)
            secret_client.set_secret(secret_name, secret_value)
            logger.info("Stored secret %s in Key Vault", secret_name)
            return True
        except Exception as e:
            logger.error("Could not store Key Vault secret %s: %s", secret_name, e)
            return False

    async def get_agent_status(self, instance_name: str, tenant_slug: str) -> dict:
        """Check the live status of an OpenClaw agent pod.

        Returns a dict with:
          - phase: CR phase (e.g. "Running", "Pending")
          - ready: bool — all containers running
          - containers_ready: int
          - containers_total: int
          - message: human-readable status string
        """
        namespace = f"tenant-{tenant_slug}"
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._check_pod_status, namespace, instance_name
        )

    @staticmethod
    def _check_pod_status(namespace: str, instance_name: str) -> dict:
        """Check OpenClawInstance CR phase and pod container readiness."""
        from kubernetes import client

        core_v1, custom_api = _get_k8s_clients()

        result = {
            "phase": "Unknown",
            "ready": False,
            "containers_ready": 0,
            "containers_total": 0,
            "message": "Checking...",
        }

        # Check CR status
        try:
            cr = custom_api.get_namespaced_custom_object(
                group=OPENCLAW_GROUP,
                version=OPENCLAW_VERSION,
                namespace=namespace,
                plural=OPENCLAW_PLURAL,
                name=instance_name,
            )
            status = cr.get("status", {})
            result["phase"] = status.get("phase", "Pending")
            result["ready"] = status.get("ready", False)
        except client.ApiException:
            result["message"] = "Instance not found"
            return result

        # Check pod readiness for container counts
        try:
            pods = core_v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=f"app.kubernetes.io/instance={instance_name}",
            )
            if pods.items:
                pod = pods.items[0]
                statuses = pod.status.container_statuses or []
                result["containers_total"] = len(statuses)
                result["containers_ready"] = sum(
                    1 for cs in statuses if cs.ready
                )

                # Identify which containers are NOT ready
                not_ready_names = [cs.name for cs in statuses if not cs.ready]

                if result["containers_ready"] == result["containers_total"] and result["containers_total"] > 0:
                    result["ready"] = True
                    result["message"] = "Running"
                elif pod.status.phase == "Running" and result["containers_ready"] >= 1:
                    # The WhatsApp bridge container stays not-ready until QR is
                    # scanned.  Chromium sidecar also takes extra time.
                    # Treat the agent as operationally ready when the
                    # core containers are up and only non-critical ones are pending.
                    # openclaw's readiness probe checks WA link state on
                    # the gateway-proxy /readyz endpoint, so it stays
                    # not-ready until WA is linked.
                    non_critical = {"whatsapp", "wa-bridge", "whatsapp-bridge", "wa", "chromium", "openclaw"}
                    only_non_critical_pending = all(
                        n.lower() in non_critical for n in not_ready_names
                    )
                    if only_non_critical_pending:
                        result["ready"] = True
                        result["message"] = "Running (awaiting WhatsApp link)"
                    else:
                        result["message"] = f"Starting ({result['containers_ready']}/{result['containers_total']} ready)"
                else:
                    # Check for init containers still running
                    init_statuses = pod.status.init_container_statuses or []
                    pending_inits = [s.name for s in init_statuses if not s.ready]
                    if pending_inits:
                        result["message"] = "Initializing"
                    else:
                        result["message"] = f"Starting ({result['containers_ready']}/{result['containers_total']} ready)"
            else:
                result["message"] = "Waiting for pod"
        except client.ApiException:
            result["message"] = "Could not check pod"

        return result

    async def get_pod_url(self, instance_name: str, tenant_slug: str, port: int = 18789) -> Optional[str]:
        """Return a URL to reach the OpenClaw gateway-proxy.

        Tries the ClusterIP service first (port 18789 → targetPort 18790)
        which is allowed by the tenant NetworkPolicy.  When the pod is
        not ready the service has no endpoints, so we fall back to the
        pod IP on the gateway-proxy port (18790) directly.
        """
        namespace = f"tenant-{tenant_slug}"
        # Check if the service has endpoints (pod is ready)
        loop = asyncio.get_event_loop()
        has_endpoints = await loop.run_in_executor(
            None, self._service_has_endpoints, namespace, instance_name,
        )
        if has_endpoints:
            return f"http://{instance_name}.{namespace}.svc.cluster.local:{port}"
        # Fall back to pod IP (bypasses readiness gate)
        pod_ip = await loop.run_in_executor(
            None, self._get_pod_ip, namespace, instance_name,
        )
        if pod_ip:
            return f"http://{pod_ip}:18790"
        return None

    @staticmethod
    def _service_has_endpoints(namespace: str, instance_name: str) -> bool:
        core_v1, _ = _get_k8s_clients()
        try:
            ep = core_v1.read_namespaced_endpoints(instance_name, namespace)
            for subset in (ep.subsets or []):
                if subset.addresses:
                    return True
        except Exception:
            pass
        return False

    @staticmethod
    def _get_pod_ip(namespace: str, instance_name: str) -> Optional[str]:
        core_v1, _ = _get_k8s_clients()
        try:
            pods = core_v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=f"app.kubernetes.io/instance={instance_name}",
            )
            if pods.items and pods.items[0].status.pod_ip:
                return pods.items[0].status.pod_ip
        except Exception:
            pass
        return None

    # In-flight WhatsApp link sessions keyed by instance_name.
    # Each entry is {"task": asyncio.Task, "status": "linking"|"connected"|"failed", "error": str|None}
    _wa_link_sessions: dict = {}

    async def get_whatsapp_qr(
        self, instance_name: str, tenant_slug: str
    ) -> dict:
        """Connect to the OpenClaw gateway via WebSocket, retrieve
        the WhatsApp Web login QR code, and keep the WS alive in a
        background task so the pairing handshake can complete.

        Returns a dict with ``qr_data_url`` (base64 PNG data-url) and
        ``message`` on success, or raises on failure.
        """
        # Cancel any previous session for this instance
        prev = self._wa_link_sessions.pop(instance_name, None)
        if prev and not prev["task"].done():
            prev["task"].cancel()

        pod_url = await self.get_pod_url(instance_name, tenant_slug)
        if not pod_url:
            raise RuntimeError("Could not resolve OpenClaw pod IP")

        # Convert http://ip:port to ws://ip:port
        ws_url = pod_url.replace("http://", "ws://", 1) + "/"
        origin = pod_url  # Origin header must match the gateway host

        try:
            import websockets  # type: ignore

            ws = await websockets.connect(
                ws_url,
                additional_headers={"Origin": origin},
                open_timeout=10,
            )

            try:
                # 1. Read connect.challenge
                raw = await asyncio.wait_for(ws.recv(), timeout=5)
                challenge = json.loads(raw)
                if challenge.get("event") != "connect.challenge":
                    await ws.close()
                    raise RuntimeError(f"Unexpected first frame: {challenge.get('event')}")

                # 2. Send JSON-RPC connect (no device key, no token needed
                #    with auth.mode=none + dangerouslyDisableDeviceAuth)
                connect_req = {
                    "type": "req",
                    "id": str(uuid.uuid4()),
                    "method": "connect",
                    "params": {
                        "minProtocol": 3,
                        "maxProtocol": 3,
                        "client": {
                            "id": "openclaw-control-ui",
                            "version": "control-ui",
                            "platform": "linux",
                            "mode": "webchat",
                            "instanceId": f"aiplatform-{instance_name}",
                        },
                        "role": "operator",
                        "scopes": [
                            "operator.admin",
                            "operator.read",
                            "operator.write",
                            "operator.approvals",
                            "operator.pairing",
                        ],
                        "caps": ["tool-events"],
                        "userAgent": "aiplatform-proxy/1.0",
                        "locale": "en-US",
                    },
                }
                await ws.send(json.dumps(connect_req))
                resp_raw = await asyncio.wait_for(ws.recv(), timeout=10)
                connect_resp = json.loads(resp_raw)
                if not connect_resp.get("ok"):
                    await ws.close()
                    err = connect_resp.get("error", {})
                    raise RuntimeError(
                        f"WS connect failed: {err.get('message', 'unknown')}"
                    )

                # 3. Request WhatsApp QR via web.login.start
                login_req = {
                    "type": "req",
                    "id": str(uuid.uuid4()),
                    "method": "web.login.start",
                    "params": {"force": True, "timeoutMs": 30000},
                }
                await ws.send(json.dumps(login_req))

                # Read responses, skipping events
                qr_result = None
                for _ in range(20):
                    raw = await asyncio.wait_for(ws.recv(), timeout=35)
                    msg = json.loads(raw)
                    if msg.get("type") == "event":
                        continue
                    if msg.get("type") == "res":
                        if msg.get("ok"):
                            payload = msg.get("payload", {})
                            qr_result = {
                                "qr_data_url": payload.get("qrDataUrl"),
                                "message": payload.get("message"),
                            }
                            break
                        err = msg.get("error", {})
                        await ws.close()
                        raise RuntimeError(
                            f"web.login.start failed: {err.get('message', 'unknown')}"
                        )

                if not qr_result:
                    await ws.close()
                    raise RuntimeError("No response received for web.login.start")

                # 4. Keep WS alive in background — call web.login.wait
                #    so the pairing handshake can complete (up to 2 minutes)
                session = {"task": None, "status": "linking", "error": None}
                task = asyncio.create_task(
                    self._whatsapp_link_wait(ws, instance_name, session)
                )
                session["task"] = task
                self._wa_link_sessions[instance_name] = session
                logger.info(
                    "WhatsApp QR returned for %s — background link session started",
                    instance_name,
                )
                return qr_result

            except Exception:
                # On any error during QR retrieval, close the WS
                try:
                    await ws.close()
                except Exception:
                    pass
                raise

        except ImportError:
            raise RuntimeError(
                "websockets package not installed — add it to requirements.txt"
            )
        except asyncio.TimeoutError:
            raise RuntimeError("Timeout waiting for OpenClaw gateway response")

    async def _whatsapp_link_wait(
        self, ws, instance_name: str, session: dict
    ) -> None:
        """Background task: call web.login.wait and keep the WS open so
        the WhatsApp pairing handshake can complete."""
        try:
            wait_req = {
                "type": "req",
                "id": str(uuid.uuid4()),
                "method": "web.login.wait",
                "params": {"timeoutMs": 120000},
            }
            await ws.send(json.dumps(wait_req))

            for _ in range(30):
                raw = await asyncio.wait_for(ws.recv(), timeout=130)
                msg = json.loads(raw)
                if msg.get("type") == "event":
                    logger.debug("WA link event: %s", msg.get("event"))
                    continue
                if msg.get("type") == "res":
                    payload = msg.get("payload", {})
                    if msg.get("ok") and payload.get("connected"):
                        session["status"] = "connected"
                        logger.info("WhatsApp linked successfully for %s", instance_name)
                    else:
                        session["status"] = "failed"
                        err = msg.get("error", {})
                        session["error"] = err.get("message", payload.get("message", "link failed"))
                        logger.warning("WhatsApp link failed for %s: %s", instance_name, session["error"])
                    return
        except asyncio.CancelledError:
            logger.info("WhatsApp link session cancelled for %s", instance_name)
            session["status"] = "failed"
            session["error"] = "cancelled"
        except Exception as e:
            logger.error("WhatsApp link wait error for %s: %s", instance_name, e)
            session["status"] = "failed"
            session["error"] = str(e)
        finally:
            try:
                await ws.close()
            except Exception:
                pass

    def get_whatsapp_link_status(self, instance_name: str) -> dict:
        """Return the current status of an in-flight WhatsApp link session."""
        session = self._wa_link_sessions.get(instance_name)
        if not session:
            return {"status": "none"}
        return {"status": session["status"], "error": session.get("error")}

    async def whatsapp_logout(
        self, instance_name: str, tenant_slug: str
    ) -> dict:
        """Disconnect and logout from WhatsApp via the OpenClaw gateway.

        Sends the ``channels.logout`` RPC which clears credentials
        on the pod, requiring a fresh QR scan to re-link.
        """
        pod_url = await self.get_pod_url(instance_name, tenant_slug)
        if not pod_url:
            raise RuntimeError("Could not resolve OpenClaw pod IP")

        ws_url = pod_url.replace("http://", "ws://", 1) + "/"
        try:
            import websockets

            async with websockets.connect(
                ws_url,
                additional_headers={"Origin": pod_url},
                open_timeout=10,
                close_timeout=5,
            ) as ws:
                await asyncio.wait_for(ws.recv(), timeout=5)  # challenge
                await ws.send(json.dumps({
                    "type": "req", "id": str(uuid.uuid4()), "method": "connect",
                    "params": {
                        "minProtocol": 3, "maxProtocol": 3,
                        "client": {
                            "id": "openclaw-control-ui",
                            "version": "control-ui",
                            "platform": "linux",
                            "mode": "webchat",
                            "instanceId": f"logout-{instance_name}-{uuid.uuid4()}",
                        },
                        "role": "operator",
                        "scopes": [
                            "operator.admin",
                            "operator.read",
                            "operator.write",
                        ],
                        "caps": [],
                    },
                }))
                # Read connect response
                for _ in range(10):
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    msg = json.loads(raw)
                    if msg.get("type") == "res":
                        if not msg.get("ok"):
                            raise RuntimeError("WS connect failed")
                        break

                # Send channels.logout
                await ws.send(json.dumps({
                    "type": "req", "id": str(uuid.uuid4()),
                    "method": "channels.logout",
                    "params": {"channel": "whatsapp"},
                }))
                for _ in range(10):
                    raw = await asyncio.wait_for(ws.recv(), timeout=15)
                    msg = json.loads(raw)
                    if msg.get("type") == "event":
                        continue
                    if msg.get("type") == "res":
                        if msg.get("ok"):
                            logger.info("WhatsApp logout completed for %s", instance_name)
                            return {"status": "logged_out"}
                        err = msg.get("error", {})
                        raise RuntimeError(
                            f"channels.logout failed: {err.get('message', 'unknown')}"
                        )
                raise RuntimeError("No response for channels.logout")
        except ImportError:
            raise RuntimeError("websockets package not installed")
        except asyncio.TimeoutError:
            raise RuntimeError("Timeout waiting for logout response")

    async def get_channel_status(
        self, instance_name: str, tenant_slug: str
    ) -> dict:
        """Query live channel status from the OpenClaw pod via WebSocket."""
        pod_url = await self.get_pod_url(instance_name, tenant_slug)
        if not pod_url:
            return {}

        ws_url = pod_url.replace("http://", "ws://", 1) + "/"
        try:
            import websockets

            async with websockets.connect(
                ws_url,
                additional_headers={"Origin": pod_url},
                open_timeout=5,
                close_timeout=3,
            ) as ws:
                await asyncio.wait_for(ws.recv(), timeout=3)  # challenge
                await ws.send(json.dumps({
                    "type": "req", "id": str(uuid.uuid4()), "method": "connect",
                    "params": {
                        "minProtocol": 3, "maxProtocol": 3,
                        "client": {"id": "openclaw-control-ui", "version": "control-ui",
                                   "platform": "linux", "mode": "webchat",
                                   "instanceId": f"status-{instance_name}"},
                        "role": "operator",
                        "scopes": ["operator.admin"],
                        "caps": [],
                    },
                }))
                # Read connect response, skipping any events
                connect_ok = False
                for _ in range(10):
                    raw = await asyncio.wait_for(ws.recv(), timeout=5)
                    msg = json.loads(raw)
                    if msg.get("type") == "event":
                        # Extract channel status from health event if available
                        if msg.get("event") == "health":
                            payload = msg.get("payload", {})
                            if payload.get("channels"):
                                return payload
                        continue
                    if msg.get("type") == "res":
                        connect_ok = msg.get("ok", False)
                        break
                if not connect_ok:
                    return {}

                await ws.send(json.dumps({
                    "type": "req", "id": str(uuid.uuid4()),
                    "method": "channels.status", "params": {},
                }))
                for _ in range(10):
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                    if msg.get("type") == "event":
                        continue
                    if msg.get("type") == "res" and msg.get("ok"):
                        payload = msg.get("payload", {})
                        # Normalize to same shape as old health response
                        return {"channels": payload.get("channels", {})}
                    break
        except Exception as e:
            logger.debug("channel status check failed for %s: %s", instance_name, e)
        return {}

    async def list_groups(
        self, instance_name: str, tenant_slug: str
    ) -> list[dict]:
        """Return WhatsApp & Telegram groups the agent is connected to.

        Uses two data sources and merges results:
        1. ``sessions.list`` via WS — returns groups with active sessions
           (includes display names / subjects).
        2. Filesystem scan of WhatsApp sender-key files — discovers ALL
           groups the phone participates in, even those without sessions.

        Each returned dict contains: ``key``, ``display_name``, ``channel``,
        ``group_id``, ``message_count``, ``last_message_at``, and
        ``has_session`` (bool).
        """
        namespace = f"tenant-{tenant_slug}"
        pod_name = f"{instance_name}-0"

        # ------------------------------------------------------------------
        # Source 1: WS sessions.list (groups with active conversations)
        # ------------------------------------------------------------------
        session_groups: dict[str, dict] = {}  # keyed by group_id
        pod_url = await self.get_pod_url(instance_name, tenant_slug)
        if pod_url:
            ws_url = pod_url.replace("http://", "ws://", 1) + "/"
            try:
                import websockets

                async with websockets.connect(
                    ws_url,
                    additional_headers={"Origin": pod_url},
                    open_timeout=5,
                    close_timeout=3,
                ) as ws:
                    await asyncio.wait_for(ws.recv(), timeout=3)  # challenge
                    await ws.send(json.dumps({
                        "type": "req", "id": str(uuid.uuid4()), "method": "connect",
                        "params": {
                            "minProtocol": 3, "maxProtocol": 3,
                            "client": {"id": "openclaw-control-ui", "version": "control-ui",
                                       "platform": "linux", "mode": "webchat",
                                       "instanceId": f"groups-{instance_name}"},
                            "role": "operator",
                            "scopes": ["operator.admin"],
                            "caps": [],
                        },
                    }))
                    connect_ok = False
                    for _ in range(10):
                        raw = await asyncio.wait_for(ws.recv(), timeout=5)
                        msg = json.loads(raw)
                        if msg.get("type") == "event":
                            continue
                        if msg.get("type") == "res":
                            connect_ok = msg.get("ok", False)
                            break
                    if connect_ok:
                        await ws.send(json.dumps({
                            "type": "req", "id": str(uuid.uuid4()),
                            "method": "sessions.list", "params": {},
                        }))
                        for _ in range(10):
                            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                            if msg.get("type") == "event":
                                continue
                            if msg.get("type") == "res" and msg.get("ok"):
                                for s in msg.get("payload", {}).get("sessions", []):
                                    if s.get("kind") != "group":
                                        continue
                                    key = s.get("key", "")
                                    channel = s.get("channel") or ""
                                    # Extract bare JID from session key
                                    # e.g. "main:whatsapp:group:120363...@g.us" → "120363...@g.us"
                                    import re as _re
                                    jid_match = _re.search(r'(\d[\d@.\-]+@g\.us)', key)
                                    group_id = jid_match.group(1) if jid_match else (key.split(":", 1)[1] if ":" in key else key)
                                    if not channel:
                                        if "whatsapp" in key:
                                            channel = "whatsapp"
                                        elif "telegram" in key:
                                            channel = "telegram"
                                    raw_name = s.get("subject") or s.get("displayName") or s.get("name") or ""
                                    # Detect JID-like display names (no real group name)
                                    is_jid = not raw_name or "@g.us" in raw_name
                                    session_groups[group_id] = {
                                        "key": key,
                                        "display_name": raw_name if not is_jid else group_id,
                                        "channel": channel,
                                        "group_id": group_id,
                                        "has_name": not is_jid,
                                        "message_count": s.get("messageCount", 0),
                                        "last_message_at": s.get("lastMessageAt"),
                                        "has_session": True,
                                    }
                            break
            except Exception as e:
                logger.debug("list_groups WS failed for %s: %s", instance_name, e)

        # ------------------------------------------------------------------
        # Source 2: Cached Baileys group metadata (wa_group_meta_cache.json)
        # ------------------------------------------------------------------
        baileys_groups: dict[str, dict] = {}  # keyed by JID
        try:
            loop = asyncio.get_event_loop()
            raw = await loop.run_in_executor(
                None,
                self._exec_in_pod,
                namespace,
                pod_name,
                ["cat", "/home/openclaw/.openclaw/wa_group_meta_cache.json"],
            )
            if raw and raw.strip().startswith("{"):
                import json as _json
                data = _json.loads(raw.strip())
                for jid, meta in data.items():
                    baileys_groups[jid] = {
                        "subject": meta.get("subject", ""),
                        "size": meta.get("size", 0),
                    }
                logger.info("Loaded %d groups from wa_group_meta_cache.json", len(baileys_groups))
        except Exception as e:
            logger.warning("list_groups Baileys cache read failed for %s: %s", instance_name, e)

        # ------------------------------------------------------------------
        # Source 3 (fallback): Filesystem scan for sender-key files
        # ------------------------------------------------------------------
        fs_jids: set[str] = set()
        if not baileys_groups:
            try:
                loop = asyncio.get_event_loop()
                raw = await loop.run_in_executor(
                    None,
                    self._exec_in_pod,
                    namespace,
                    pod_name,
                    [
                        "find",
                        "/home/openclaw/.openclaw/credentials/whatsapp",
                        "-name", "sender-key-*@g.us*",
                        "-type", "f",
                    ],
                )
                import re
                for line in raw.splitlines():
                    m = re.search(r"sender-key-(?:memory-)?(.+?@g\.us)", line)
                    if m:
                        fs_jids.add(m.group(1))
            except Exception as e:
                logger.debug("list_groups filesystem scan failed for %s: %s", instance_name, e)

        # ------------------------------------------------------------------
        # Merge all sources
        # ------------------------------------------------------------------
        seen_jids: set[str] = set()
        groups: list[dict] = []

        def _bare_jid(gid: str) -> str:
            """Extract the raw JID (e.g. '...@g.us') from a session key."""
            import re as _re
            m = _re.search(r'(\d[\d@.\-]+@g\.us)', gid)
            return m.group(1) if m else gid

        # Add session groups first (they may have message counts)
        for gid, g in session_groups.items():
            bare = _bare_jid(gid)
            seen_jids.add(bare)
            # Enrich with Baileys group name if session had a JID-like name
            if not g.get("has_name") and bare in baileys_groups:
                subj = baileys_groups[bare].get("subject", "")
                if subj:
                    g["display_name"] = subj
                    g["has_name"] = True
            groups.append(g)

        # Add Baileys-discovered groups not already in sessions
        for jid, meta in baileys_groups.items():
            if jid in seen_jids:
                continue
            seen_jids.add(jid)
            subj = meta.get("subject", "")
            groups.append({
                "key": f"whatsapp:group:{jid}",
                "display_name": subj if subj else jid,
                "channel": "whatsapp",
                "group_id": jid,
                "has_name": bool(subj),
                "message_count": 0,
                "last_message_at": None,
                "has_session": False,
            })

        # Add filesystem-only groups (fallback when Baileys fetch fails)
        for jid in sorted(fs_jids):
            if jid in seen_jids:
                continue
            seen_jids.add(jid)
            groups.append({
                "key": f"whatsapp:group:{jid}",
                "display_name": jid,
                "channel": "whatsapp",
                "group_id": jid,
                "has_name": False,
                "message_count": 0,
                "last_message_at": None,
                "has_session": False,
            })

        return groups

    async def deploy_agent(
        self,
        agent_id: str,
        agent_name: str,
        tenant_slug: str,
        system_prompt: str,
        model_endpoint: Optional[dict],
        openclaw_config: Optional[dict],
    ) -> dict:
        """Deploy an OpenClawInstance for the given agent.

        Returns a dict with instance_name and gateway_url.
        """
        safe_name = _sanitize_name(agent_name)[:40]
        instance_name = f"oc-{safe_name}-{agent_id[:8]}".rstrip("-")
        namespace = f"tenant-{tenant_slug}"

        # Resolve model from the platform's model endpoint
        model_id, base_url = self._resolve_model(model_endpoint)

        # If no base URL from model endpoint, fetch from Key Vault
        if not base_url:
            base_url = await self._get_kv_secret("azure-openai-api-base")
            if base_url:
                base_url = base_url.rstrip("/") + "/openai/v1"

        # Build the CR body
        cr = await self._build_cr(
            instance_name=instance_name,
            namespace=namespace,
            agent_id=agent_id,
            system_prompt=system_prompt or "You are a helpful assistant.",
            model_id=model_id,
            base_url=base_url,
            openclaw_config=openclaw_config or {},
        )

        # Build K8s Secret with values from Key Vault (OpenClaw reads via envFrom)
        secret_data = await self._build_k8s_secret(instance_name, openclaw_config or {})

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None, self._apply_secret_and_cr, namespace, instance_name, secret_data, cr
        )

        gateway_url = f"http://{instance_name}.{namespace}.svc.cluster.local:18789"

        logger.info(
            "Deployed OpenClaw instance %s in %s for agent %s (gateway: %s)",
            instance_name, namespace, agent_id, gateway_url,
        )

        # Launch background task to auto-approve device pairing once pod is ready
        asyncio.ensure_future(
            self._auto_approve_devices(instance_name, namespace)
        )

        return {
            "instance_name": instance_name,
            "gateway_url": gateway_url,
        }

    async def _auto_approve_devices(
        self, instance_name: str, namespace: str, timeout_s: int = 300
    ) -> None:
        """Wait for the OpenClaw pod to be ready, then approve pending device pairing requests.

        The OpenClaw CLI inside the container auto-registers as a device on first
        startup but requires manual approval.  Without approval the agent's
        built-in tools (e.g. WhatsApp message send) fail with 'pairing required'.
        """
        import time

        pod_name = f"{instance_name}-0"
        deadline = time.monotonic() + timeout_s

        # 1. Poll until the pod is Running + Ready
        loop = asyncio.get_event_loop()
        while time.monotonic() < deadline:
            try:
                ready = await loop.run_in_executor(
                    None, self._is_pod_ready, namespace, pod_name
                )
                if ready:
                    break
            except Exception:
                pass
            await asyncio.sleep(5)
        else:
            logger.warning(
                "Timed out waiting for pod %s/%s to be ready for device approval",
                namespace, pod_name,
            )
            return

        # 2. Retry approval a few times — the CLI registers its device
        #    pairing request asynchronously after gateway startup.
        import json as _json
        for attempt in range(4):
            await asyncio.sleep(10 if attempt == 0 else 15)
            try:
                output = await loop.run_in_executor(
                    None,
                    self._exec_in_pod,
                    namespace,
                    pod_name,
                    ["openclaw", "devices", "list", "--json"],
                )
                # stdout may contain stderr lines before the JSON object
                json_start = output.find("{")
                if json_start < 0:
                    logger.debug("No JSON in devices list output (attempt %d): %s", attempt, output[:200])
                    continue
                devices = _json.loads(output[json_start:])
                pending = devices.get("pending", [])
                if not pending:
                    logger.info("No pending device pairing in %s/%s (attempt %d)", namespace, pod_name, attempt)
                    return
                for dev in pending:
                    req_id = dev.get("requestId") or dev.get("id", "")
                    if not req_id:
                        continue
                    await loop.run_in_executor(
                        None,
                        self._exec_in_pod,
                        namespace,
                        pod_name,
                        ["openclaw", "devices", "approve", req_id],
                    )
                    logger.info(
                        "Auto-approved device pairing %s in %s/%s",
                        req_id, namespace, pod_name,
                    )
                return
            except Exception:
                logger.warning(
                    "Failed to auto-approve devices in %s/%s (attempt %d)",
                    namespace, pod_name, attempt, exc_info=True,
                )

    @staticmethod
    def _is_pod_ready(namespace: str, pod_name: str) -> bool:
        """Check if a pod is Running and all containers are Ready."""
        core_v1, _ = _get_k8s_clients()
        pod = core_v1.read_namespaced_pod(name=pod_name, namespace=namespace)
        if pod.status.phase != "Running":
            return False
        for cs in (pod.status.container_statuses or []):
            if not cs.ready:
                return False
        return True

    @staticmethod
    def _exec_in_pod(
        namespace: str, pod_name: str, command: list[str], container: str = "openclaw"
    ) -> str:
        """Execute a command inside a pod and return stdout only."""
        from kubernetes.stream import stream as k8s_stream

        core_v1, _ = _get_k8s_clients()
        client = k8s_stream(
            core_v1.connect_get_namespaced_pod_exec,
            name=pod_name,
            namespace=namespace,
            container=container,
            command=command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _preload_content=False,
        )
        client.run_forever(timeout=60)
        stdout = client.read_stdout() or ""
        client.close()
        return stdout

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

        # If no base URL from model endpoint, fetch from Key Vault
        if not base_url:
            base_url = await self._get_kv_secret("azure-openai-api-base")
            if base_url:
                base_url = base_url.rstrip("/") + "/openai/v1"

        cr = await self._build_cr(
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

    # Reasoning-capable models (used for model spec in CR config)
    _REASONING_MODELS = {"gpt-5.4", "gpt-5.2-codex", "o1", "o3", "o3-mini", "o4-mini"}

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
            base_url = (api_base or "").rstrip("/")
            if base_url and not base_url.endswith("/openai/v1"):
                base_url = f"{base_url}/openai/v1"
            return f"azure-openai-responses/{model}", base_url
        else:
            return f"openai/{model}", api_base

    # ------------------------------------------------------------------ #
    #  CR builders (zero secrets in YAML)
    # ------------------------------------------------------------------ #

    async def _build_cr(
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
            if not allowed:
                # Fetch default allowed users from Key Vault
                allowed = await self._get_kv_secret_as_list("TELEGRAMALLOWFROM")
            if allowed:
                channels_config["telegram"]["allowFrom"] = [str(u) for u in allowed]

            # Channel-level instructions for Telegram
            tg_instructions = channels.get("telegram_channel_instructions", "")
            if tg_instructions:
                channels_config["telegram"]["instructions"] = tg_instructions

        # WhatsApp channel — uses QR-code session linking (no static secret)
        whatsapp = openclaw_config.get("whatsapp") or {}
        if whatsapp.get("whatsapp_enabled"):
            dm_policy = whatsapp.get("whatsapp_dm_policy", "allowlist")
            group_policy = whatsapp.get("whatsapp_group_policy", "allowlist")
            wa_config: dict = {
                "enabled": True,
                "dmPolicy": dm_policy,
                "groupPolicy": group_policy,
            }
            wa_allowed = whatsapp.get("whatsapp_allowed_phones", [])
            if dm_policy == "open":
                wa_config["allowFrom"] = ["*"]
            elif wa_allowed:
                wa_config["allowFrom"] = [str(p) for p in wa_allowed]
            else:
                # OpenClaw requires at least one entry in allowFrom for
                # "allowlist" mode.  When no phones are configured yet,
                # use "pairing" mode which blocks all DMs until approved
                # — effectively the same as an empty allowlist.
                wa_config["dmPolicy"] = "pairing"

            # Per-group rules: each rule can override policy, requireMention, allowFrom
            group_rules = whatsapp.get("whatsapp_group_rules", [])
            groups_cfg: dict = {}
            if group_rules:
                for rule in group_rules:
                    gid = rule.get("group_jid")
                    if not gid:
                        # Pending groups (name-only, no JID) are skipped —
                        # OpenClaw can't match incoming messages by Hebrew
                        # name, only by JID.  They'll be auto-resolved when
                        # the Refresh endpoint runs.
                        continue
                    # Strip session-key prefix (e.g. "main:whatsapp:group:...@g.us" → "...@g.us")
                    import re as _re
                    m = _re.search(r'(\d[\d@.\-]+@g\.us)', gid)
                    if m:
                        gid = m.group(1)
                    if rule.get("policy") == "blocked":
                        # Skip blocked groups — under allowlist groupPolicy,
                        # unlisted groups are ignored automatically
                        continue
                    entry: dict = {
                        "requireMention": rule.get("require_mention", False),
                    }
                    # NOTE: OpenClaw's config schema only allows "requireMention"
                    # and "allowFrom" per group. Group names and per-group
                    # instructions are injected via the system prompt in
                    # agent_execution.py instead.
                    rule_phones = rule.get("allowed_phones", [])
                    if rule.get("policy") == "allowlist" and rule_phones:
                        entry["allowFrom"] = [str(p) for p in rule_phones]
                    groups_cfg[gid] = entry
            if not groups_cfg:
                if group_policy == "open":
                    # Open policy: respond to all groups without requiring @mention
                    groups_cfg = {"*": {"requireMention": False}}
                else:
                    # Allowlist with no rules: set groupPolicy to "open" so
                    # OpenClaw tracks incoming group messages (enabling
                    # discovery), but require @mention so the agent does
                    # NOT respond unless explicitly addressed.
                    wa_config["groupPolicy"] = "open"
                    groups_cfg = {"*": {"requireMention": True}}
            if groups_cfg:
                wa_config["groups"] = groups_cfg

            # Channel-level instructions for WhatsApp
            wa_instructions = whatsapp.get("whatsapp_channel_instructions", "")
            if wa_instructions:
                wa_config["instructions"] = wa_instructions

            channels_config["whatsapp"] = wa_config

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
                "api": "openai-completions",
                "authHeader": False,
                "headers": {"api-key": "${AZURE_API_KEY}"},
                "models": [
                    {
                        "id": model_name,
                        "name": f"{model_name} (Azure)",
                        "reasoning": model_name in OpenClawService._REASONING_MODELS,
                        "input": ["text", "image"],
                        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                        "contextWindow": 1047576,
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
                    "memorySearch": {
                        "enabled": True,
                        "experimental": {"sessionMemory": True},
                    },
                }
            },
            "session": {
                "scope": "per-sender",
                "dmScope": "per-peer",
            },
            "tools": {
                "sessions": {"visibility": "agent"},
            },
        }

        # Gateway config — enable OpenAI-compatible HTTP endpoints so the
        # platform can route playground chat through /v1/chat/completions.
        # auth mode=none: gateway is bound to loopback (pod-internal only)
        # and protected by NetworkPolicy, so no additional auth needed.
        # The platform still sends X-Forwarded-User and X-Openclaw-Scopes
        # headers for identity/scope propagation.
        raw_config["gateway"] = {
            "auth": {
                "mode": "none",
            },
            "bind": "loopback",
            "controlUi": {
                "allowedOrigins": ["*"],
            },
            "trustedProxies": ["127.0.0.0/8"],
            "http": {
                "endpoints": {
                    "chatCompletions": {"enabled": True},
                }
            },
        }

        if channels_config:
            raw_config["channels"] = channels_config
        if mcp_servers:
            raw_config["agents"]["defaults"]["mcpServers"] = mcp_servers

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
                "image": {
                    "repository": OPENCLAW_IMAGE_REPO,
                    "tag": OPENCLAW_IMAGE_TAG,
                    "pullPolicy": "Always",
                },
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

        # Gmail / Himalaya email skill
        gmail_config = openclaw_config.get("gmail") or {}
        gmail_email = gmail_config.get("gmail_email") or gmail_config.get("email")
        if gmail_email:
            skills = cr["spec"].get("skills", [])
            if "himalaya" not in skills:
                skills.append("himalaya")
            cr["spec"]["skills"] = skills
            cr["spec"]["runtimeDeps"] = {"pnpm": True}

            display_name = gmail_config.get("gmail_display_name") or gmail_config.get("display_name", "OpenClaw Agent")

            # Build himalaya TOML config.
            # Use auth.cmd to resolve the password from the GMAIL_APP_PASSWORD
            # env var at runtime (auth.raw doesn't expand env vars).
            himalaya_toml = (
                "[accounts.gmail]\n"
                f'email = "{gmail_email}"\n'
                f'display-name = "{display_name}"\n'
                "default = true\n"
                "\n"
                'backend.type = "imap"\n'
                'backend.host = "imap.gmail.com"\n'
                "backend.port = 993\n"
                'backend.encryption.type = "tls"\n'
                f'backend.login = "{gmail_email}"\n'
                'backend.auth.type = "password"\n'
                'backend.auth.cmd = "printenv GMAIL_APP_PASSWORD"\n'
                "\n"
                'message.send.backend.type = "smtp"\n'
                'message.send.backend.host = "smtp.gmail.com"\n'
                "message.send.backend.port = 587\n"
                'message.send.backend.encryption.type = "start-tls"\n'
                f'message.send.backend.login = "{gmail_email}"\n'
                'message.send.backend.auth.type = "password"\n'
                'message.send.backend.auth.cmd = "printenv GMAIL_APP_PASSWORD"\n'
                "\n"
                'folder.sent.name = "[Gmail]/Sent Mail"\n'
                'folder.drafts.name = "[Gmail]/Drafts"\n'
                'folder.trash.name = "[Gmail]/Trash"\n'
            )

            # Place config as an initialFile (no '/' in key).
            # HIMALAYA_CONFIG env var tells himalaya where to find its config
            # since ~/.config is read-only in the container.
            cr["spec"].setdefault("env", []).append(
                {"name": "HIMALAYA_CONFIG", "value": "/home/openclaw/.openclaw/workspace/himalaya-config.toml"}
            )

            # Init container to download himalaya binary — the "himalaya"
            # skill only ships documentation, not the actual CLI binary.
            cr["spec"].setdefault("initContainers", []).append({
                "name": "install-himalaya",
                "image": "curlimages/curl:latest",
                "command": ["sh", "-c",
                    "curl -sL https://github.com/pimalaya/himalaya/releases/download/v1.2.0/himalaya.x86_64-linux.tgz "
                    "| tar xz -C /shared-bin/ && chmod +x /shared-bin/himalaya"
                ],
                "volumeMounts": [{"name": "shared-bin", "mountPath": "/shared-bin"}],
            })
            cr["spec"].setdefault("extraVolumes", []).append(
                {"name": "shared-bin", "emptyDir": {}}
            )
            cr["spec"].setdefault("extraVolumeMounts", []).append(
                {"name": "shared-bin", "mountPath": "/home/openclaw/.openclaw/.local/bin/himalaya", "subPath": "himalaya"}
            )

            cr["spec"]["workspace"] = {
                "initialFiles": {
                    "himalaya-config.toml": himalaya_toml,
                    "CLAUDE.md": (
                        "# Agent Instructions\n\n"
                        "## Email Access\n"
                        f"You have access to the Gmail account {gmail_email} via the Himalaya CLI.\n"
                        "ALWAYS use the `himalaya` command-line tool for any email operations "
                        "— NEVER open Gmail in a browser.\n\n"
                        "Common commands:\n"
                        '- List unread emails: `himalaya envelope list --folder INBOX "not flag seen"`\n'
                        "- List all emails: `himalaya envelope list --folder INBOX`\n"
                        "- Read an email: `himalaya message read <id>`\n"
                        '- Send an email: `himalaya message send "From: ' + gmail_email + '\nTo: <address>\nSubject: <subject>\n\n<body>"`\n'
                        "- Reply to an email: `himalaya message reply <id>`\n"
                        '- Search by sender: `himalaya envelope list --folder INBOX "from <pattern>"`\n'
                        '- Search by subject: `himalaya envelope list --folder INBOX "subject <pattern>"`\n'
                        "- List folders: `himalaya folder list`\n\n"
                        "Important notes:\n"
                        "- The FLAGS column shows IMAP flags: no flags = unread, `*` = flagged/starred\n"
                        "- When sending, always include the From header\n"
                        "- Gmail sent folder is `[Gmail]/Sent Mail`\n\n"
                        "When asked about email, unread messages, or Gmail, use Himalaya immediately "
                        "— do not browse to gmail.com.\n"
                    ),
                }
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
                    "keyvaultName": TENANT_KEY_VAULT_NAME,
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
    #  K8s Secret builder (fetches values from Key Vault)
    # ------------------------------------------------------------------ #

    async def _build_k8s_secret(self, instance_name: str, openclaw_config: dict) -> dict:
        """Fetch secrets from Key Vault and return K8s Secret data dict."""
        import base64

        api_key = await self._get_kv_secret("azure-openai-api-key")
        if not api_key:
            raise RuntimeError("Could not fetch azure-openai-api-key from Key Vault")

        api_base = await self._get_kv_secret("azure-openai-api-base")

        data = {
            "AZURE_API_KEY": base64.b64encode(api_key.encode()).decode(),
        }
        if api_base:
            data["AZURE_API_BASE"] = base64.b64encode(api_base.encode()).decode()

        channels = openclaw_config.get("channels") or {}
        if channels.get("telegram_enabled"):
            token_secret = channels.get("telegram_bot_token_secret", "TELEGRAMBOTTOKEN")
            bot_token = await self._get_kv_secret(token_secret)
            if bot_token:
                data["TELEGRAM_BOT_TOKEN"] = base64.b64encode(bot_token.encode()).decode()

        # Gmail app password
        gmail_config = openclaw_config.get("gmail") or {}
        gmail_email = gmail_config.get("gmail_email") or gmail_config.get("email")
        if gmail_email:
            gmail_secret = gmail_config.get("gmail_app_password_secret") or gmail_config.get("app_password_secret", "gmail-app-password")
            gmail_pw = await self._get_kv_secret(gmail_secret)
            if gmail_pw:
                data["GMAIL_APP_PASSWORD"] = base64.b64encode(gmail_pw.encode()).decode()

        return data

    # ------------------------------------------------------------------ #
    #  K8s operations (run in thread pool)
    # ------------------------------------------------------------------ #

    @staticmethod
    def _apply_secret_and_cr(namespace: str, instance_name: str, secret_data: dict, cr: dict) -> None:
        """Create/update K8s Secret + OpenClawInstance CR."""
        from kubernetes import client

        core_v1, custom_api = _get_k8s_clients()

        # 1. Create or update K8s Secret
        secret_name = f"{instance_name}-secrets"
        secret_body = client.V1Secret(
            api_version="v1",
            kind="Secret",
            metadata=client.V1ObjectMeta(name=secret_name, namespace=namespace),
            type="Opaque",
            data=secret_data,
        )
        try:
            core_v1.create_namespaced_secret(namespace=namespace, body=secret_body)
            logger.info("Created K8s Secret %s in %s", secret_name, namespace)
        except client.ApiException as e:
            if e.status == 409:
                core_v1.replace_namespaced_secret(
                    name=secret_name, namespace=namespace, body=secret_body
                )
                logger.info("Updated K8s Secret %s in %s", secret_name, namespace)
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
        """Replace an existing OpenClawInstance CR (full replace, not merge)."""
        from datetime import datetime, timezone
        from kubernetes import client

        _, custom_api = _get_k8s_clients()
        try:
            # Fetch existing to get resourceVersion (required for replace)
            existing = custom_api.get_namespaced_custom_object(
                group=OPENCLAW_GROUP,
                version=OPENCLAW_VERSION,
                namespace=namespace,
                plural=OPENCLAW_PLURAL,
                name=instance_name,
            )
            cr["metadata"]["resourceVersion"] = existing["metadata"]["resourceVersion"]
            # Force reconciliation by bumping a timestamp annotation
            annotations = cr.get("metadata", {}).get("annotations") or {}
            annotations["aiplatform.io/last-deployed"] = datetime.now(timezone.utc).isoformat()
            cr["metadata"]["annotations"] = annotations
            custom_api.replace_namespaced_custom_object(
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
        """Delete OpenClawInstance CR, K8s Secret, and SecretProviderClass."""
        from kubernetes import client

        core_v1, custom_api = _get_k8s_clients()

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

        # Delete K8s Secret
        try:
            core_v1.delete_namespaced_secret(
                name=f"{instance_name}-secrets",
                namespace=namespace,
            )
            logger.info("Deleted Secret %s-secrets", instance_name)
        except client.ApiException as e:
            if e.status != 404:
                raise

        # Delete SecretProviderClass (legacy cleanup)
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
