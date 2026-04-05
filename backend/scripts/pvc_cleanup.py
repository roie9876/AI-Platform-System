"""PVC Cleanup & Archival — Archives old OpenClaw session data to Azure Blob Storage.

Runs as a K8s CronJob. For each OpenClaw agent pod:
1. Lists session files older than RETENTION_DAYS
2. Tars and uploads them to Azure Blob Storage
3. Deletes the archived files from the PVC

Environment variables:
  STORAGE_ACCOUNT_NAME  — Azure storage account name
  RETENTION_DAYS        — Days to keep session files (default: 7)
  DRY_RUN               — If "true", log actions without deleting (default: false)
"""

import asyncio
import io
import logging
import os
import tarfile
import time
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("pvc-cleanup")

STORAGE_ACCOUNT_NAME = os.getenv("STORAGE_ACCOUNT_NAME", "")
CONTAINER_NAME = "agent-archives"
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "7"))
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"

# OpenClaw workspace path inside the pod
WORKSPACE_BASE = "/home/openclaw/.openclaw"
# Directories that contain session/ephemeral data eligible for cleanup
SESSION_DIRS = ["sessions", "workspace/sessions", "workspace/.sessions"]


def _get_k8s_clients():
    from kubernetes import client, config

    try:
        config.load_incluster_config()
    except Exception:
        config.load_kube_config()
    return client.CoreV1Api()


def _get_blob_client():
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    credential = DefaultAzureCredential()
    account_url = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
    return BlobServiceClient(account_url=account_url, credential=credential)


def _find_openclaw_pods(core_v1) -> list[dict]:
    """Find all OpenClaw agent pods across tenant namespaces."""
    pods = []
    namespaces = core_v1.list_namespace(label_selector="app.kubernetes.io/part-of=aiplatform")
    tenant_namespaces = [
        ns.metadata.name for ns in namespaces.items
        if ns.metadata.name.startswith("tenant-")
    ]

    # Also check all namespaces starting with tenant-
    all_ns = core_v1.list_namespace()
    for ns in all_ns.items:
        name = ns.metadata.name
        if name.startswith("tenant-") and name not in tenant_namespaces:
            tenant_namespaces.append(name)

    for ns in tenant_namespaces:
        try:
            pod_list = core_v1.list_namespaced_pod(
                namespace=ns,
                label_selector="aiplatform/agent-type=openclaw",
            )
            for pod in pod_list.items:
                if pod.status.phase == "Running":
                    pods.append({
                        "name": pod.metadata.name,
                        "namespace": ns,
                        "agent_id": pod.metadata.labels.get("aiplatform/agent-id", "unknown"),
                    })
        except Exception as e:
            logger.warning("Failed to list pods in %s: %s", ns, e)

    return pods


def _exec_in_pod(core_v1, namespace: str, pod_name: str, command: list[str]) -> str:
    """Execute a command in a pod and return stdout."""
    from kubernetes.stream import stream

    resp = stream(
        core_v1.connect_get_namespaced_pod_exec,
        pod_name,
        namespace,
        command=command,
        stderr=True,
        stdin=False,
        stdout=True,
        tty=False,
    )
    return resp


def _find_old_files(core_v1, namespace: str, pod_name: str) -> list[str]:
    """Find session files older than RETENTION_DAYS in the pod."""
    old_files = []
    for session_dir in SESSION_DIRS:
        full_path = f"{WORKSPACE_BASE}/{session_dir}"
        try:
            # Check if directory exists
            result = _exec_in_pod(
                core_v1, namespace, pod_name,
                ["sh", "-c", f"test -d {full_path} && echo EXISTS || echo MISSING"],
            )
            if "MISSING" in result:
                continue

            # Find files older than RETENTION_DAYS
            result = _exec_in_pod(
                core_v1, namespace, pod_name,
                ["find", full_path, "-type", "f", "-mtime", f"+{RETENTION_DAYS}"],
            )
            files = [f.strip() for f in result.strip().split("\n") if f.strip()]
            old_files.extend(files)
        except Exception as e:
            logger.warning("Failed to scan %s in %s/%s: %s", session_dir, namespace, pod_name, e)

    return old_files


def _read_file_from_pod(core_v1, namespace: str, pod_name: str, file_path: str) -> bytes:
    """Read a file from a pod as bytes."""
    result = _exec_in_pod(
        core_v1, namespace, pod_name,
        ["cat", file_path],
    )
    return result.encode("utf-8", errors="replace")


def _archive_and_upload(
    core_v1, blob_service, namespace: str, pod_name: str,
    agent_id: str, files: list[str],
) -> int:
    """Archive files from pod into a tar.gz and upload to blob storage."""
    if not files:
        return 0

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    blob_name = f"{namespace}/{agent_id}/{timestamp}-sessions.tar.gz"

    # Build tar archive in memory
    tar_buffer = io.BytesIO()
    archived_count = 0

    with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
        for file_path in files:
            try:
                content = _read_file_from_pod(core_v1, namespace, pod_name, file_path)
                # Use relative path from workspace base
                arcname = file_path.replace(WORKSPACE_BASE + "/", "")
                info = tarfile.TarInfo(name=arcname)
                info.size = len(content)
                info.mtime = int(time.time())
                tar.addfile(info, io.BytesIO(content))
                archived_count += 1
            except Exception as e:
                logger.warning("Failed to read %s from %s/%s: %s", file_path, namespace, pod_name, e)

    if archived_count == 0:
        return 0

    # Upload to blob storage
    tar_buffer.seek(0)
    container_client = blob_service.get_container_client(CONTAINER_NAME)
    container_client.upload_blob(
        name=blob_name,
        data=tar_buffer,
        overwrite=True,
    )
    logger.info("Uploaded archive %s (%d files, %d bytes)", blob_name, archived_count, tar_buffer.tell())
    return archived_count


def _delete_files_from_pod(core_v1, namespace: str, pod_name: str, files: list[str]) -> int:
    """Delete archived files from the pod PVC."""
    deleted = 0
    # Delete in batches of 50 to avoid argument list too long
    for i in range(0, len(files), 50):
        batch = files[i:i + 50]
        try:
            _exec_in_pod(
                core_v1, namespace, pod_name,
                ["rm", "-f"] + batch,
            )
            deleted += len(batch)
        except Exception as e:
            logger.warning("Failed to delete batch in %s/%s: %s", namespace, pod_name, e)

    # Clean up empty directories
    for session_dir in SESSION_DIRS:
        full_path = f"{WORKSPACE_BASE}/{session_dir}"
        try:
            _exec_in_pod(
                core_v1, namespace, pod_name,
                ["find", full_path, "-type", "d", "-empty", "-delete"],
            )
        except Exception:
            pass

    return deleted


def main():
    logger.info(
        "PVC Cleanup starting — retention=%d days, storage=%s, dry_run=%s",
        RETENTION_DAYS, STORAGE_ACCOUNT_NAME, DRY_RUN,
    )

    core_v1 = _get_k8s_clients()
    blob_service = _get_blob_client() if STORAGE_ACCOUNT_NAME else None

    pods = _find_openclaw_pods(core_v1)
    logger.info("Found %d OpenClaw pods", len(pods))

    total_archived = 0
    total_deleted = 0

    for pod in pods:
        pod_name = pod["name"]
        namespace = pod["namespace"]
        agent_id = pod["agent_id"]

        logger.info("Processing %s/%s (agent: %s)", namespace, pod_name, agent_id)

        old_files = _find_old_files(core_v1, namespace, pod_name)
        if not old_files:
            logger.info("  No old files found")
            continue

        logger.info("  Found %d files older than %d days", len(old_files), RETENTION_DAYS)

        if DRY_RUN:
            for f in old_files[:10]:
                logger.info("  [DRY RUN] Would archive: %s", f)
            if len(old_files) > 10:
                logger.info("  [DRY RUN] ... and %d more", len(old_files) - 10)
            continue

        # Archive to blob storage
        if blob_service:
            archived = _archive_and_upload(
                core_v1, blob_service, namespace, pod_name, agent_id, old_files,
            )
            total_archived += archived
        else:
            logger.warning("  No storage account configured, skipping archive")

        # Delete from PVC
        deleted = _delete_files_from_pod(core_v1, namespace, pod_name, old_files)
        total_deleted += deleted
        logger.info("  Deleted %d files from PVC", deleted)

    logger.info(
        "PVC Cleanup complete — archived=%d, deleted=%d across %d pods",
        total_archived, total_deleted, len(pods),
    )


if __name__ == "__main__":
    main()
