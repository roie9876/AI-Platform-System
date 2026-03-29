"""E2E Tenant Lifecycle Test — runs inside the api-gateway pod."""
import asyncio
import sys


async def test():
    from app.services.tenant_service import TenantService
    svc = TenantService()

    results = []
    passed = 0
    failed = 0

    def check(step, desc, condition, detail=""):
        nonlocal passed, failed
        status = "PASS" if condition else "FAIL"
        if condition:
            passed += 1
        else:
            failed += 1
        msg = f"  [{status}] Step {step}: {desc}"
        if detail:
            msg += f" — {detail}"
        print(msg)
        results.append((step, desc, status))

    print("=" * 60)
    print("  E2E TENANT LIFECYCLE TEST")
    print("=" * 60)

    # --- STEP 1: Create tenant ---
    print("\n>>> STEP 1: Create tenant 'test-lifecycle'")
    try:
        tenant = await svc.create_tenant("Test Lifecycle", "test-lifecycle")
        tenant_id = tenant["id"]
        check(1, "Tenant created", True, f"id={tenant_id}, status={tenant.get('status')}")
    except Exception as e:
        check(1, "Tenant created", False, str(e))
        print("\nCannot continue without tenant. Aborting.")
        return 1

    # --- STEP 2: Verify in list ---
    print("\n>>> STEP 2: Verify tenant appears in list")
    tenants = await svc.list_tenants()
    found = [t for t in tenants if t["slug"] == "test-lifecycle"]
    check(2, "Tenant in list", len(found) == 1, f"found={len(found)}")

    deleted_in_list = [t for t in tenants if t.get("status") == "deleted"]
    check("2b", "No deleted tenants in list", len(deleted_in_list) == 0, f"deleted_count={len(deleted_in_list)}")

    # --- STEP 3: Verify K8s namespace ---
    print("\n>>> STEP 3: Check K8s namespace created")
    try:
        from app.services.tenant_provisioning import _get_k8s_client
        k8s = _get_k8s_client()
        core_v1 = k8s.CoreV1Api()
        apps_v1 = k8s.AppsV1Api()
        ns = core_v1.read_namespace("tenant-test-lifecycle")
        check(3, "K8s namespace exists", ns.status.phase == "Active", f"phase={ns.status.phase}")
    except Exception as e:
        check(3, "K8s namespace exists", False, str(e)[:120])

    # --- STEP 3b: Verify hybrid model — only agent-executor + tool-executor ---
    print("\n>>> STEP 3b: Verify hybrid model (only per-tenant compute)")
    try:
        deps = apps_v1.list_namespaced_deployment("tenant-test-lifecycle")
        dep_names = sorted([d.metadata.name for d in deps.items])
        expected = ["agent-executor", "tool-executor"]
        check("3b", "Hybrid model correct", dep_names == expected,
              f"deployments={dep_names}")
    except Exception as e:
        check("3b", "Hybrid model correct", False, str(e)[:120])

    # --- STEP 3c: Verify ServiceAccount exists ---
    print("\n>>> STEP 3c: Verify ServiceAccount in tenant namespace")
    try:
        sa = core_v1.read_namespaced_service_account("aiplatform-workload", "tenant-test-lifecycle")
        check("3c", "ServiceAccount exists", sa is not None, f"name={sa.metadata.name}")
    except Exception as e:
        check("3c", "ServiceAccount exists", False, str(e)[:120])

    # --- STEP 4: Suspend ---
    print("\n>>> STEP 4: Transition active -> suspended")
    try:
        updated = await svc.transition_state(tenant_id, "suspended")
        check(4, "Suspended", updated["status"] == "suspended", f"status={updated['status']}")
    except Exception as e:
        check(4, "Suspended", False, str(e))

    # --- STEP 5: Reactivate ---
    print("\n>>> STEP 5: Transition suspended -> active")
    try:
        updated = await svc.transition_state(tenant_id, "active")
        check(5, "Reactivated", updated["status"] == "active", f"status={updated['status']}")
    except Exception as e:
        check(5, "Reactivated", False, str(e))

    # --- STEP 6: Invalid transition test ---
    print("\n>>> STEP 6: Invalid transition active -> deleted (should fail)")
    try:
        await svc.transition_state(tenant_id, "deleted")
        check(6, "Invalid transition rejected", False, "Should have raised error")
    except ValueError:
        check(6, "Invalid transition rejected", True, "ValueError raised correctly")
    except Exception as e:
        check(6, "Invalid transition rejected", False, str(e))

    # --- STEP 7: Suspend + Deactivate ---
    print("\n>>> STEP 7: active -> suspended -> deactivated")
    try:
        await svc.transition_state(tenant_id, "suspended")
        updated = await svc.transition_state(tenant_id, "deactivated")
        check(7, "Deactivated", updated["status"] == "deactivated", f"status={updated['status']}")
    except Exception as e:
        check(7, "Deactivated", False, str(e))

    # --- STEP 8: Delete ---
    print("\n>>> STEP 8: Delete tenant (deactivated -> deleted)")
    try:
        result = await svc.delete_tenant(tenant_id)
        check(8, "Deleted", result["status"] == "deleted", f"status={result['status']}")
    except Exception as e:
        check(8, "Deleted", False, str(e))

    # --- STEP 9: Verify removed from list ---
    print("\n>>> STEP 9: Verify tenant NOT in list")
    tenants = await svc.list_tenants()
    found = [t for t in tenants if t["slug"] == "test-lifecycle"]
    check(9, "Not in tenant list", len(found) == 0, f"found={len(found)}")

    # --- STEP 10: K8s namespace cleanup ---
    print("\n>>> STEP 10: Verify K8s namespace deleted/terminating")
    try:
        ns = core_v1.read_namespace("tenant-test-lifecycle")
        terminating = ns.status.phase == "Terminating"
        check(10, "K8s namespace cleaned up", terminating, f"phase={ns.status.phase}")
    except Exception as e:
        err = str(e)
        is_gone = "404" in err or "Not Found" in err
        check(10, "K8s namespace cleaned up", is_gone, "namespace deleted" if is_gone else err[:80])

    # --- STEP 11: Re-create with same slug ---
    print("\n>>> STEP 11: Re-create tenant with same slug 'test-lifecycle'")
    try:
        tenant2 = await svc.create_tenant("Test Lifecycle v2", "test-lifecycle")
        check(11, "Slug reuse works", True, f"new_id={tenant2['id']}, status={tenant2.get('status')}")
    except Exception as e:
        check(11, "Slug reuse works", False, str(e))
        print("\n" + "=" * 60)
        print(f"  RESULTS: {passed} passed, {failed} failed")
        print("=" * 60)
        return 1

    # --- STEP 12: Cleanup ---
    print("\n>>> STEP 12: Cleanup re-created tenant")
    try:
        t2_id = tenant2["id"]
        t2_status = tenant2.get("status", "provisioning")
        # If stuck in provisioning (namespace race), delete directly
        if t2_status == "provisioning":
            result = await svc.delete_tenant(t2_id)
        else:
            await svc.transition_state(t2_id, "suspended")
            await svc.transition_state(t2_id, "deactivated")
            result = await svc.delete_tenant(t2_id)
        check(12, "Cleanup complete", result["status"] == "deleted")
    except Exception as e:
        check(12, "Cleanup complete", False, str(e))

    # --- SUMMARY ---
    print("\n" + "=" * 60)
    print(f"  RESULTS: {passed} passed, {failed} failed out of {passed + failed} checks")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    rc = asyncio.run(test())
    sys.exit(rc)
