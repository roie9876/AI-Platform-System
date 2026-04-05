"""Tenant provisioning service — K8s namespace, seed data, admin user creation."""

import asyncio
import logging
import os

from app.repositories.config_repo import CatalogEntryRepository
from app.repositories.tool_repo import ToolRepository
from app.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)

# ACR image registry — read from env (set via configmap) or fallback
ACR_REGISTRY = os.getenv("ACR_REGISTRY", os.getenv("ACR_LOGIN_SERVER", ""))


def _get_acr_registry() -> str:
    """Get ACR registry at runtime (env may be set after module import)."""
    return os.getenv("ACR_REGISTRY", os.getenv("ACR_LOGIN_SERVER", ACR_REGISTRY))

DEFAULT_TOOLS = [
    {
        "name": "web_search",
        "type": "built-in",
        "description": "Search the web",
        "config": {},
        "is_platform_tool": True,
    },
    {
        "name": "code_interpreter",
        "type": "built-in",
        "description": "Execute Python code and return stdout, stderr, and exit code.",
        "config": {},
        "is_platform_tool": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
            },
            "required": ["code"],
        },
    },
]

DEFAULT_CATALOG = [
    {
        "name": "Getting Started",
        "type": "template",
        "description": "Default agent template",
        "config": {"system_prompt": "You are a helpful assistant."},
    },
]

# Per-tenant compute services — only agent-executor and tool-executor
# run in tenant namespaces.  The rest of the control plane (api-gateway,
# workflow-engine, mcp-proxy) is shared in the 'aiplatform' namespace and
# serves all tenants via Cosmos DB partition keys.
TENANT_MICROSERVICES = [
    {"name": "agent-executor", "image_suffix": "aiplatform-agent-executor:latest", "port": 8000},
    {"name": "tool-executor", "image_suffix": "aiplatform-tool-executor:latest", "port": 8000},
]

# Name of the workload-identity service account to mirror into tenant namespaces
WORKLOAD_SA_NAME = "aiplatform-workload"


def _get_k8s_client():
    """Load K8s client — in-cluster when running in a pod, kubeconfig otherwise."""
    from kubernetes import client, config

    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client


class TenantProvisioningService:
    def __init__(self) -> None:
        self.tool_repo = ToolRepository()
        self.catalog_repo = CatalogEntryRepository()
        self.user_repo = UserRepository()

    async def provision_tenant(self, tenant: dict) -> None:
        tenant_id = tenant["id"]
        slug = tenant["slug"]
        admin_email = tenant["admin_email"]
        tenant_name = tenant.get("name", slug)

        logger.info("Starting provisioning for tenant %s (slug=%s)", tenant_id, slug)

        await self._provision_k8s_namespace(slug)
        await self._seed_default_data(tenant_id)
        await self._create_admin_user(tenant_id, admin_email)

        # Create Entra ID security group if not already provided
        entra_group_id = tenant.get("entra_group_id", "")
        if not entra_group_id:
            entra_group_id = await self._create_entra_group(tenant_name, slug, admin_email)
            if entra_group_id:
                # Store the group ID back on the tenant document
                from app.services.tenant_service import TenantService

                svc = TenantService()
                await svc.update_tenant(tenant_id, {"entra_group_id": entra_group_id})
                logger.info("Stored entra_group_id=%s on tenant %s", entra_group_id, tenant_id)

        # Transition to active
        from app.services.tenant_service import TenantService

        service = TenantService()
        await service.transition_state(tenant_id, "active")

        logger.info("Provisioning complete for tenant %s", tenant_id)

    async def _provision_k8s_namespace(self, slug: str) -> None:
        namespace = f"tenant-{slug}"
        logger.info("Provisioning K8s namespace %s for tenant slug: %s", namespace, slug)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._create_k8s_resources, slug, namespace)

        logger.info("K8s namespace %s provisioned successfully", namespace)

    @staticmethod
    def _create_k8s_resources(slug: str, namespace: str) -> None:
        """Create all K8s resources for a tenant namespace (runs in thread pool)."""
        k8s = _get_k8s_client()
        core_v1 = k8s.CoreV1Api()
        apps_v1 = k8s.AppsV1Api()
        networking_v1 = k8s.NetworkingV1Api()
        autoscaling_v2 = k8s.AutoscalingV2Api()

        labels = {
            "app.kubernetes.io/part-of": "aiplatform",
            "aiplatform/tenant": slug,
        }

        # 1. Create Namespace
        ns_body = k8s.V1Namespace(
            metadata=k8s.V1ObjectMeta(name=namespace, labels=labels)
        )
        try:
            core_v1.create_namespace(body=ns_body)
            logger.info("Created namespace %s", namespace)
        except k8s.ApiException as e:
            if e.status == 409:
                logger.info("Namespace %s already exists", namespace)
            else:
                raise

        # 2. ResourceQuota
        quota = k8s.V1ResourceQuota(
            metadata=k8s.V1ObjectMeta(name="tenant-quota", namespace=namespace),
            spec=k8s.V1ResourceQuotaSpec(
                hard={
                    "requests.cpu": "4",
                    "requests.memory": "8Gi",
                    "limits.cpu": "8",
                    "limits.memory": "16Gi",
                    "pods": "20",
                    "services": "10",
                    "persistentvolumeclaims": "20",
                }
            ),
        )
        try:
            core_v1.create_namespaced_resource_quota(namespace, body=quota)
            logger.info("Created ResourceQuota in %s", namespace)
        except k8s.ApiException as e:
            if e.status != 409:
                raise

        # 3. LimitRange
        limit_range = k8s.V1LimitRange(
            metadata=k8s.V1ObjectMeta(name="tenant-limits", namespace=namespace),
            spec=k8s.V1LimitRangeSpec(
                limits=[
                    k8s.V1LimitRangeItem(
                        type="Container",
                        default={"cpu": "500m", "memory": "512Mi"},
                        default_request={"cpu": "100m", "memory": "128Mi"},
                        max={"cpu": "2", "memory": "4Gi"},
                        min={"cpu": "5m", "memory": "8Mi"},
                    )
                ]
            ),
        )
        try:
            core_v1.create_namespaced_limit_range(namespace, body=limit_range)
            logger.info("Created LimitRange in %s", namespace)
        except k8s.ApiException as e:
            if e.status != 409:
                raise

        # 4. ServiceAccount — mirror workload identity SA into tenant namespace
        sa_body = k8s.V1ServiceAccount(
            metadata=k8s.V1ObjectMeta(
                name=WORKLOAD_SA_NAME,
                namespace=namespace,
                labels=labels,
                annotations={
                    "azure.workload.identity/client-id": os.getenv("AZURE_CLIENT_ID", ""),
                },
            )
        )
        try:
            core_v1.create_namespaced_service_account(namespace, body=sa_body)
            logger.info("Created ServiceAccount %s in %s", WORKLOAD_SA_NAME, namespace)
        except k8s.ApiException as e:
            if e.status != 409:
                raise

        # 5. NetworkPolicy — tenant isolation
        net_pol = networking_v1.create_namespaced_network_policy(
            namespace,
            body={
                "apiVersion": "networking.k8s.io/v1",
                "kind": "NetworkPolicy",
                "metadata": {"name": "tenant-isolation", "namespace": namespace},
                "spec": {
                    "podSelector": {},
                    "policyTypes": ["Ingress", "Egress"],
                    "ingress": [
                        {"from": [{"namespaceSelector": {"matchLabels": {"app.kubernetes.io/name": "alb-controller"}}}]},
                        {"from": [{"podSelector": {}}]},
                    ],
                    "egress": [
                        {
                            "to": [{"namespaceSelector": {}}],
                            "ports": [
                                {"protocol": "UDP", "port": 53},
                                {"protocol": "TCP", "port": 53},
                            ],
                        },
                        {
                            "to": [{"ipBlock": {"cidr": "0.0.0.0/0", "except": ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]}}],
                            "ports": [{"protocol": "TCP", "port": 443}],
                        },
                        {
                            "to": [{"podSelector": {}}],
                            "ports": [{"protocol": "TCP", "port": 8000}],
                        },
                    ],
                },
            },
        )
        logger.info("Created NetworkPolicy in %s", namespace)

        # 6. Deploy per-tenant compute services (agent-executor, tool-executor)
        acr = _get_acr_registry()
        if not acr:
            raise RuntimeError("ACR_REGISTRY / ACR_LOGIN_SERVER env var not set — cannot create tenant deployments")

        for svc in TENANT_MICROSERVICES:
            svc_labels = {**labels, "app": svc["name"]}
            image = f"{acr}/{svc['image_suffix']}"

            # Deployment
            deployment = k8s.V1Deployment(
                metadata=k8s.V1ObjectMeta(name=svc["name"], namespace=namespace, labels=svc_labels),
                spec=k8s.V1DeploymentSpec(
                    replicas=1,
                    selector=k8s.V1LabelSelector(match_labels={"app": svc["name"]}),
                    template=k8s.V1PodTemplateSpec(
                        metadata=k8s.V1ObjectMeta(labels=svc_labels),
                        spec=k8s.V1PodSpec(
                            service_account_name="aiplatform-workload",
                            containers=[
                                k8s.V1Container(
                                    name=svc["name"],
                                    image=image,
                                    ports=[k8s.V1ContainerPort(container_port=svc["port"])],
                                    resources=k8s.V1ResourceRequirements(
                                        requests={"cpu": "100m", "memory": "128Mi"},
                                        limits={"cpu": "500m", "memory": "512Mi"},
                                    ),
                                    env=[
                                        k8s.V1EnvVar(name="TENANT_ID", value=slug),
                                        k8s.V1EnvVar(name="SERVICE_NAME", value=svc["name"]),
                                    ],
                                )
                            ],
                        ),
                    ),
                ),
            )
            try:
                apps_v1.create_namespaced_deployment(namespace, body=deployment)
                logger.info("Created Deployment %s in %s", svc["name"], namespace)
            except k8s.ApiException as e:
                if e.status != 409:
                    raise

            # Service
            service = k8s.V1Service(
                metadata=k8s.V1ObjectMeta(name=svc["name"], namespace=namespace, labels=svc_labels),
                spec=k8s.V1ServiceSpec(
                    selector={"app": svc["name"]},
                    ports=[k8s.V1ServicePort(port=svc["port"], target_port=svc["port"])],
                ),
            )
            try:
                core_v1.create_namespaced_service(namespace, body=service)
                logger.info("Created Service %s in %s", svc["name"], namespace)
            except k8s.ApiException as e:
                if e.status != 409:
                    raise

            # Autoscaling — KEDA ScaledObject for agent-executor (scale-to-zero
            # via Service Bus queue), HPA for everything else.
            if svc["name"] == "agent-executor":
                sb_conn = os.getenv("SERVICE_BUS_CONNECTION_STRING", "")
                custom_api = k8s.CustomObjectsApi()

                # Secret with Service Bus connection string for KEDA trigger auth
                sb_secret = k8s.V1Secret(
                    metadata=k8s.V1ObjectMeta(
                        name="keda-servicebus-auth",
                        namespace=namespace,
                    ),
                    string_data={"connection-string": sb_conn},
                )
                try:
                    core_v1.create_namespaced_secret(namespace, body=sb_secret)
                    logger.info("Created KEDA Service Bus secret in %s", namespace)
                except k8s.ApiException as e:
                    if e.status != 409:
                        raise

                # TriggerAuthentication
                trigger_auth = {
                    "apiVersion": "keda.sh/v1alpha1",
                    "kind": "TriggerAuthentication",
                    "metadata": {"name": "servicebus-auth", "namespace": namespace},
                    "spec": {
                        "secretTargetRef": [
                            {
                                "parameter": "connection",
                                "name": "keda-servicebus-auth",
                                "key": "connection-string",
                            }
                        ]
                    },
                }
                try:
                    custom_api.create_namespaced_custom_object(
                        group="keda.sh", version="v1alpha1",
                        namespace=namespace, plural="triggerauthentications",
                        body=trigger_auth,
                    )
                    logger.info("Created TriggerAuthentication in %s", namespace)
                except k8s.ApiException as e:
                    if e.status != 409:
                        raise

                # ScaledObject — scale-to-zero on Service Bus queue depth
                scaled_object = {
                    "apiVersion": "keda.sh/v1alpha1",
                    "kind": "ScaledObject",
                    "metadata": {"name": f"{svc['name']}-scaledobject", "namespace": namespace},
                    "spec": {
                        "scaleTargetRef": {"name": svc["name"]},
                        "minReplicaCount": 0,
                        "maxReplicaCount": 10,
                        "pollingInterval": 5,
                        "cooldownPeriod": 300,
                        "triggers": [
                            {
                                "type": "azure-servicebus",
                                "metadata": {
                                    "queueName": "agent-requests",
                                    "messageCount": "1",
                                },
                                "authenticationRef": {"name": "servicebus-auth"},
                            }
                        ],
                    },
                }
                try:
                    custom_api.create_namespaced_custom_object(
                        group="keda.sh", version="v1alpha1",
                        namespace=namespace, plural="scaledobjects",
                        body=scaled_object,
                    )
                    logger.info("Created KEDA ScaledObject for %s in %s", svc["name"], namespace)
                except k8s.ApiException as e:
                    if e.status != 409:
                        raise
            else:
                # Standard HPA for non-agent-executor services
                hpa = {
                    "apiVersion": "autoscaling/v2",
                    "kind": "HorizontalPodAutoscaler",
                    "metadata": {"name": f"{svc['name']}-hpa", "namespace": namespace},
                    "spec": {
                        "scaleTargetRef": {
                            "apiVersion": "apps/v1",
                            "kind": "Deployment",
                            "name": svc["name"],
                        },
                        "minReplicas": 1,
                        "maxReplicas": 3,
                        "metrics": [
                            {"type": "Resource", "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": 70}}},
                            {"type": "Resource", "resource": {"name": "memory", "target": {"type": "Utilization", "averageUtilization": 80}}},
                        ],
                    },
                }
                try:
                    autoscaling_v2.create_namespaced_horizontal_pod_autoscaler(namespace, body=hpa)
                    logger.info("Created HPA for %s in %s", svc["name"], namespace)
                except k8s.ApiException as e:
                    if e.status != 409:
                        raise

        logger.info("All K8s resources created for tenant namespace %s", namespace)

    async def deprovision_tenant(self, tenant: dict) -> None:
        """Remove K8s resources and Entra group for a deleted tenant."""
        slug = tenant["slug"]
        namespace = f"tenant-{slug}"
        logger.info("Deprovisioning K8s namespace %s for tenant %s", namespace, tenant["id"])

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._delete_k8s_namespace, namespace)

        # Delete the Entra group if one was created
        entra_group_id = tenant.get("entra_group_id", "")
        if entra_group_id:
            await self._delete_entra_group(entra_group_id)

        logger.info("Deprovisioning complete for tenant %s", tenant["id"])

    @staticmethod
    def _delete_k8s_namespace(namespace: str) -> None:
        """Delete a tenant namespace — cascades all resources inside it."""
        k8s = _get_k8s_client()
        core_v1 = k8s.CoreV1Api()

        try:
            core_v1.delete_namespace(name=namespace)
            logger.info("Deleted namespace %s", namespace)
        except k8s.ApiException as e:
            if e.status == 404:
                logger.info("Namespace %s already deleted", namespace)
            else:
                raise

    async def _seed_default_data(self, tenant_id: str) -> None:
        logger.info("Seeding default data for tenant %s", tenant_id)

        for tool in DEFAULT_TOOLS:
            await self.tool_repo.create(tenant_id, {**tool})

        for entry in DEFAULT_CATALOG:
            await self.catalog_repo.create(tenant_id, {**entry})

        logger.info("Seeded %d tools and %d catalog entries", len(DEFAULT_TOOLS), len(DEFAULT_CATALOG))

    async def _create_entra_group(
        self, tenant_name: str, slug: str, admin_email: str
    ) -> str | None:
        """Create an Entra security group and add platform admins + tenant admin as members."""
        try:
            from app.services.entra_group_service import EntraGroupService

            svc = EntraGroupService()
            group_id = await svc.create_group(tenant_name, slug)
            if not group_id:
                return None

            # Collect all emails to add: platform admins + tenant admin
            emails_to_add: set[str] = set()

            # Always add platform admin(s) to every tenant group
            platform_admins = os.getenv("PLATFORM_ADMIN_EMAILS", "")
            for email in platform_admins.split(","):
                email = email.strip()
                if email and "@" in email:
                    emails_to_add.add(email.lower())

            # Also add the tenant-specific admin if different
            if admin_email and "@" in admin_email:
                emails_to_add.add(admin_email.lower())

            for email in emails_to_add:
                try:
                    added = await svc.add_member(group_id, email)
                    if not added:
                        logger.warning("Could not add '%s' to group %s", email, group_id)
                except Exception:
                    logger.exception("Error adding '%s' to group %s", email, group_id)

            return group_id
        except Exception:
            logger.exception("Entra group creation failed for tenant '%s' — continuing without it", slug)
            return None

    async def _delete_entra_group(self, group_id: str) -> None:
        """Delete the Entra security group associated with a tenant."""
        try:
            from app.services.entra_group_service import EntraGroupService

            svc = EntraGroupService()
            await svc.delete_group(group_id)
        except Exception:
            logger.exception("Entra group deletion failed for group %s — continuing", group_id)

    async def _create_admin_user(self, tenant_id: str, admin_email: str) -> None:
        existing = await self.user_repo.get_by_email(tenant_id, admin_email)
        if existing:
            logger.info("Admin user %s already exists for tenant %s", admin_email, tenant_id)
            return

        admin_user = {
            "email": admin_email,
            "full_name": "Tenant Admin",
            "role": "admin",
            "is_active": True,
        }
        await self.user_repo.create(tenant_id, admin_user)
        logger.info("Created admin user %s for tenant %s", admin_email, tenant_id)
