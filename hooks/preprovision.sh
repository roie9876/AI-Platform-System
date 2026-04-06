#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

step() { echo ""; echo -e "${BLUE}══════ $1 ══════${NC}"; }

# Validate prerequisites for azd up
echo "=== Pre-provision: Validating prerequisites ==="

# Check required CLI tools
for cmd in az kubectl helm jq; do
  if ! command -v "$cmd" &>/dev/null; then
    echo -e "${RED}ERROR: $cmd is required but not installed.${NC}"
    exit 1
  fi
done

# Validate Azure login
if ! az account show &>/dev/null; then
  echo -e "${RED}ERROR: Not logged in to Azure. Run 'az login' first.${NC}"
  exit 1
fi

# Copy environment-specific Bicep parameter file
eval "$(azd env get-values | sed 's/^/export /')"
AZURE_ENV_NAME="${AZURE_ENV_NAME:-prod}"
PARAM_FILE="infra/parameters/${AZURE_ENV_NAME}.bicepparam"
if [ -f "${PARAM_FILE}" ]; then
  cp "${PARAM_FILE}" infra/main.bicepparam
  # Fix relative path: parameters/ uses '../main.bicep', but infra/ needs './main.bicep'
  sed -i.bak "s|using '../main.bicep'|using './main.bicep'|" infra/main.bicepparam
  rm -f infra/main.bicepparam.bak
  echo "Using parameter file for environment: ${AZURE_ENV_NAME}"
else
  echo -e "${RED}ERROR: Parameter file not found: ${PARAM_FILE}${NC}"
  echo "Available environments: $(ls infra/parameters/*.bicepparam 2>/dev/null | xargs -I{} basename {} .bicepparam)"
  exit 1
fi

# ─── Step: Auto-detect deployer principal ID for RBAC ─────────────────────────

step "Deployer RBAC Setup"

DEPLOYER_OID=$(az ad signed-in-user show --query id -o tsv 2>/dev/null || echo "")
if [ -n "${DEPLOYER_OID}" ]; then
  azd env set deployerPrincipalId "${DEPLOYER_OID}"
  echo -e "  ${GREEN}✓ Deployer principal ID: ${DEPLOYER_OID}${NC}"
  echo "  RBAC roles will be assigned on Key Vault, Cosmos DB, and Service Bus."
else
  echo -e "  ${YELLOW}⚠  Could not detect deployer principal ID. Skipping deployer RBAC.${NC}"
  echo "  You can set it manually: azd env set deployerPrincipalId <your-object-id>"
fi

# ─── Step: Entra ID App Registration ─────────────────────────────────────────

step "Entra ID App Registration"

# Read entraAppClientId from the parameter file
EXISTING_CLIENT_ID=$(grep 'param entraAppClientId' "${PARAM_FILE}" | sed "s/.*= *'//" | sed "s/'.*//")

if [ -n "${EXISTING_CLIENT_ID}" ] && [ "${EXISTING_CLIENT_ID}" != "" ]; then
  echo -e "  ${GREEN}✓ Using existing App Registration: ${EXISTING_CLIENT_ID}${NC}"
  echo "  Skipping auto-creation. Ensure your app has the required API permissions and roles."
else
  echo "  No entraAppClientId found in ${PARAM_FILE} — creating App Registration..."
  echo ""
  echo -e "  ${YELLOW}⚠  This requires Global Administrator or Application Administrator role.${NC}"
  echo -e "  ${YELLOW}   The script will create an App Registration and grant admin consent.${NC}"
  echo ""

  APP_DISPLAY_NAME="AI-Agent-Platform-${AZURE_ENV_NAME}"
  AZURE_TENANT_ID=$(az account show --query tenantId -o tsv)

  # Check if app already exists (idempotent)
  EXISTING_APP=$(az ad app list --display-name "${APP_DISPLAY_NAME}" --query "[0].appId" -o tsv 2>/dev/null || echo "")

  if [ -n "${EXISTING_APP}" ]; then
    echo -e "  ${YELLOW}App Registration '${APP_DISPLAY_NAME}' already exists: ${EXISTING_APP}${NC}"
    APP_CLIENT_ID="${EXISTING_APP}"
  else
    # Create App Registration with SPA redirect URIs
    echo "  Creating App Registration: ${APP_DISPLAY_NAME}..."

    APP_CLIENT_ID=$(az ad app create \
      --display-name "${APP_DISPLAY_NAME}" \
      --sign-in-audience "AzureADMyOrg" \
      --enable-id-token-issuance true \
      --enable-access-token-issuance false \
      --query "appId" -o tsv)

    echo -e "  ${GREEN}✓ App Registration created: ${APP_CLIENT_ID}${NC}"

    # Wait for eventual consistency
    sleep 5
  fi

  APP_OBJECT_ID=$(az ad app show --id "${APP_CLIENT_ID}" --query "id" -o tsv)

  # ── Expose an API (access_as_user scope) ──────────────────────────────────
  echo "  Configuring Exposed API scope..."

  # Set Application ID URI
  az ad app update --id "${APP_CLIENT_ID}" \
    --identifier-uris "api://${APP_CLIENT_ID}" 2>/dev/null || true

  # Check if scope already exists
  EXISTING_SCOPES=$(az ad app show --id "${APP_CLIENT_ID}" --query "api.oauth2PermissionScopes[?value=='access_as_user'].id" -o tsv 2>/dev/null || echo "")

  if [ -z "${EXISTING_SCOPES}" ]; then
    SCOPE_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
    az rest --method PATCH \
      --uri "https://graph.microsoft.com/v1.0/applications/${APP_OBJECT_ID}" \
      --headers "Content-Type=application/json" \
      --body "{
        \"api\": {
          \"oauth2PermissionScopes\": [{
            \"id\": \"${SCOPE_ID}\",
            \"adminConsentDisplayName\": \"Access AI Agent Platform\",
            \"adminConsentDescription\": \"Allow the application to access AI Agent Platform on behalf of the signed-in user.\",
            \"userConsentDisplayName\": \"Access AI Agent Platform\",
            \"userConsentDescription\": \"Allow the application to access AI Agent Platform on your behalf.\",
            \"isEnabled\": true,
            \"type\": \"User\",
            \"value\": \"access_as_user\"
          }]
        }
      }"
    echo -e "  ${GREEN}✓ API scope 'access_as_user' created${NC}"
  else
    echo -e "  ${GREEN}✓ API scope 'access_as_user' already exists${NC}"
  fi

  # ── Define App Roles ──────────────────────────────────────────────────────
  echo "  Configuring App Roles..."

  ROLE_ADMIN_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
  ROLE_TENANT_ADMIN_ID=$(python3 -c "import uuid; print(uuid.uuid4())")
  ROLE_TENANT_USER_ID=$(python3 -c "import uuid; print(uuid.uuid4())")

  az rest --method PATCH \
    --uri "https://graph.microsoft.com/v1.0/applications/${APP_OBJECT_ID}" \
    --headers "Content-Type=application/json" \
    --body "{
      \"appRoles\": [
        {
          \"id\": \"${ROLE_ADMIN_ID}\",
          \"allowedMemberTypes\": [\"User\"],
          \"displayName\": \"Platform Administrator\",
          \"description\": \"Full platform administration access\",
          \"isEnabled\": true,
          \"value\": \"Platform.Admin\"
        },
        {
          \"id\": \"${ROLE_TENANT_ADMIN_ID}\",
          \"allowedMemberTypes\": [\"User\"],
          \"displayName\": \"Tenant Administrator\",
          \"description\": \"Tenant-level administration access\",
          \"isEnabled\": true,
          \"value\": \"Tenant.Admin\"
        },
        {
          \"id\": \"${ROLE_TENANT_USER_ID}\",
          \"allowedMemberTypes\": [\"User\"],
          \"displayName\": \"Tenant User\",
          \"description\": \"Standard agent user access\",
          \"isEnabled\": true,
          \"value\": \"Tenant.User\"
        }
      ]
    }" 2>/dev/null || echo -e "  ${YELLOW}App roles may already exist (non-destructive)${NC}"

  echo -e "  ${GREEN}✓ App Roles configured (Platform.Admin, Tenant.Admin, Tenant.User)${NC}"

  # ── Add SPA redirect URIs ─────────────────────────────────────────────────
  echo "  Configuring SPA redirect URIs..."

  az rest --method PATCH \
    --uri "https://graph.microsoft.com/v1.0/applications/${APP_OBJECT_ID}" \
    --headers "Content-Type=application/json" \
    --body "{
      \"spa\": {
        \"redirectUris\": [\"http://localhost:3000\"]
      }
    }"

  echo -e "  ${GREEN}✓ SPA redirect URI set (http://localhost:3000)${NC}"

  # ── Add Microsoft Graph API Permissions ───────────────────────────────────
  echo "  Configuring Microsoft Graph API permissions..."

  # Microsoft Graph App ID: 00000003-0000-0000-c000-000000000000
  # User.Read.All: df021288-bdef-4463-88db-98f22de89214
  # User.ReadWrite.All: 741f803b-c850-494e-b5df-cde7c675a1ca
  # User.Invite.All: 09850681-111b-4a89-9571-53f73d8520bd
  # Group.ReadWrite.All: 62a82d76-70ea-41e2-9197-370581804d09
  GRAPH_APP_ID="00000003-0000-0000-c000-000000000000"
  USER_READ_ALL_ID="df021288-bdef-4463-88db-98f22de89214"
  USER_RW_ALL_ID="741f803b-c850-494e-b5df-cde7c675a1ca"
  USER_INVITE_ALL_ID="09850681-111b-4a89-9571-53f73d8520bd"
  GROUP_RW_ALL_ID="62a82d76-70ea-41e2-9197-370581804d09"

  az rest --method PATCH \
    --uri "https://graph.microsoft.com/v1.0/applications/${APP_OBJECT_ID}" \
    --headers "Content-Type=application/json" \
    --body "{
      \"requiredResourceAccess\": [
        {
          \"resourceAppId\": \"${GRAPH_APP_ID}\",
          \"resourceAccess\": [
            {
              \"id\": \"${USER_READ_ALL_ID}\",
              \"type\": \"Role\"
            },
            {
              \"id\": \"${USER_RW_ALL_ID}\",
              \"type\": \"Role\"
            },
            {
              \"id\": \"${USER_INVITE_ALL_ID}\",
              \"type\": \"Role\"
            },
            {
              \"id\": \"${GROUP_RW_ALL_ID}\",
              \"type\": \"Role\"
            }
          ]
        }
      ]
    }"

  echo -e "  ${GREEN}✓ Microsoft Graph permissions added (User.Read.All, User.ReadWrite.All, User.Invite.All, Group.ReadWrite.All)${NC}"

  # ── Grant Admin Consent ───────────────────────────────────────────────────
  echo "  Granting admin consent for API permissions..."

  # Ensure Service Principal exists for the app
  az ad sp show --id "${APP_CLIENT_ID}" &>/dev/null || \
    az ad sp create --id "${APP_CLIENT_ID}" &>/dev/null

  sleep 3

  # Grant admin consent (requires Global Admin or Privileged Role Admin)
  if az ad app permission admin-consent --id "${APP_CLIENT_ID}" 2>/dev/null; then
    echo -e "  ${GREEN}✓ Admin consent granted${NC}"
  else
    echo -e "  ${YELLOW}⚠  Could not auto-grant admin consent. You may need to grant it manually:${NC}"
    echo -e "  ${YELLOW}   Azure Portal → App Registrations → ${APP_DISPLAY_NAME} → API Permissions → Grant admin consent${NC}"
  fi

  # ── Create Client Secret ─────────────────────────────────────────────────
  echo "  Creating client secret..."

  SECRET_OUTPUT=$(az ad app credential reset \
    --id "${APP_CLIENT_ID}" \
    --display-name "${AZURE_ENV_NAME}-secret" \
    --years 1 \
    --query "password" -o tsv)

  # Store secret in azd environment for postprovision.sh to seed into Key Vault
  azd env set ENTRA_CLIENT_SECRET "${SECRET_OUTPUT}"
  echo -e "  ${GREEN}✓ Client secret created and stored in azd environment${NC}"

  # ── Update Parameter File ────────────────────────────────────────────────
  echo "  Updating parameter file with new client ID..."

  sed -i.bak "s|param entraAppClientId = ''|param entraAppClientId = '${APP_CLIENT_ID}'|" "${PARAM_FILE}"
  rm -f "${PARAM_FILE}.bak"

  # Re-copy updated param file
  cp "${PARAM_FILE}" infra/main.bicepparam
  # Fix relative path: parameters/ uses '../main.bicep', but infra/ needs './main.bicep'
  sed -i.bak "s|using '../main.bicep'|using './main.bicep'|" infra/main.bicepparam
  rm -f infra/main.bicepparam.bak

  echo -e "  ${GREEN}✓ ${PARAM_FILE} updated with entraAppClientId = '${APP_CLIENT_ID}'${NC}"

  echo ""
  echo -e "  ${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
  echo -e "  ${GREEN}║  App Registration Summary                               ║${NC}"
  echo -e "  ${GREEN}╠══════════════════════════════════════════════════════════╣${NC}"
  echo -e "  ${GREEN}║  Display Name: ${APP_DISPLAY_NAME}$(printf '%*s' $((38 - ${#APP_DISPLAY_NAME})) '')║${NC}"
  echo -e "  ${GREEN}║  Client ID:    ${APP_CLIENT_ID} ║${NC}"
  echo -e "  ${GREEN}║  API Scope:    api://${APP_CLIENT_ID}/access_as_user${NC}"
  echo -e "  ${GREEN}║  App Roles:    Platform.Admin, Tenant.Admin, Tenant.User║${NC}"
  echo -e "  ${GREEN}║  Graph Perms:  User.Read/Write.All, Group.RW.All       ║${NC}"
  echo -e "  ${GREEN}║  Secret:       Stored in azd env (1-year expiry)        ║${NC}"
  echo -e "  ${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
fi

echo ""
echo -e "${GREEN}Pre-provision complete.${NC}"
echo "All prerequisites satisfied."
