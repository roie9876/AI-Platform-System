---
phase: 22-ci-cd-pipelines-github-actions
plan: 01
subsystem: infra
tags: [github-actions, docker, acr, keyvault-csi, oidc]
provides:
  - GitHub Actions build-push workflow with matrix strategy for 5 microservices + frontend
  - OIDC federated credential auth (no service principal secrets)
  - Key Vault CSI SecretProviderClass mapping secrets to K8s secrets
affects: [22-02]
requirements-completed: [DEPLOY-01, DEPLOY-02, DEPLOY-06]
duration: 4min
completed: 2026-03-26
---

# Plan 22-01: Build-Push Pipeline & Key Vault CSI Summary

**GitHub Actions workflow building 5 backend microservice + frontend Docker images, tagged with git SHA, pushed to ACR via OIDC. Key Vault CSI driver configured for secrets injection.**

## Commits
- `d6fa6c9` — feat(22-01): build-push workflow and Key Vault CSI SecretProviderClass

## Files Created
- `.github/workflows/build-push.yml` — Matrix build for 5 services + frontend, OIDC auth, ACR push
- `k8s/base/secrets/secret-provider-class.yaml` — SecretProviderClass mapping 4 Key Vault secrets
- `k8s/base/kustomization.yaml` — Added secrets resource

---
*Phase: 22-ci-cd-pipelines-github-actions*
*Completed: 2026-03-26*
