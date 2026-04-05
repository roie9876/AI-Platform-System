@description('Azure region for all resources')
param location string

@description('Environment name used in resource naming')
param environmentName string = 'prod'

@description('Principal ID of workload identity for Key Vault Secrets User role')
param workloadIdentityPrincipalId string

@description('Client ID of workload identity (stored as secret for pod consumption)')
param workloadIdentityClientId string

@description('Cosmos DB document endpoint (stored as secret for pod consumption)')
param cosmosEndpoint string

@description('Entra ID SPA application client ID (for user authentication token validation)')
param entraAppClientId string

@description('Service Bus namespace FQDN')
param serviceBusNamespace string = ''

@description('Application Insights connection string')
param appInsightsConnectionString string = ''

@description('Platform admin email addresses (comma-separated)')
param platformAdminEmails string = ''

@description('Entra admin group ID for platform admins')
param entraAdminGroupId string = ''

@description('Object ID of the deployer principal for admin RBAC access')
param deployerPrincipalId string = ''

@description('Azure AI Services endpoint (auto-provisioned)')
param aiServicesEndpoint string = ''

@description('Azure AI Services account name (for key lookup)')
param aiServicesAccountName string = ''

@description('Resource ID of Log Analytics workspace for diagnostics (optional)')
param logAnalyticsWorkspaceId string = ''

@description('Azure AD tenant ID')
param tenantId string = subscription().tenantId

@description('Tags to apply to all resources')
param tags object = {}

// Key Vault name max 24 chars: stumsft-aiplat-prod-kv = 22 chars
resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'stumsft-aiplat-${environmentName}-kv'
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

// Key Vault Secrets User role assignment for workload identity
resource kvSecretsUserRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, workloadIdentityPrincipalId, '4633458b-17de-408a-b874-0445c86b69e6')
  scope: vault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Key Vault Secrets Officer role for deployer (admin can read/write secrets in portal & CLI)
resource kvSecretsOfficerDeployer 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(vault.id, deployerPrincipalId, 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
  scope: vault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7') // Key Vault Secrets Officer
    principalId: deployerPrincipalId
    principalType: 'User'
  }
}

// ============================================================================
// Secrets — auto-seeded from Bicep deployment outputs (no hardcoded values)
// ============================================================================

resource secretCosmosEndpoint 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'cosmos-endpoint'
  properties: {
    value: cosmosEndpoint
  }
}

resource secretEntraClientId 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'entra-client-id'
  properties: {
    value: entraAppClientId
  }
}

resource secretEntraTenantId 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'entra-tenant-id'
  properties: {
    value: tenantId
  }
}

resource secretWorkloadClientId 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'workload-client-id'
  properties: {
    value: workloadIdentityClientId
  }
}

resource secretServiceBusNamespace 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(serviceBusNamespace)) {
  parent: vault
  name: 'service-bus-namespace'
  properties: {
    value: serviceBusNamespace
  }
}

resource secretAppInsightsCs 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(appInsightsConnectionString)) {
  parent: vault
  name: 'appinsights-connection-string'
  properties: {
    value: appInsightsConnectionString
  }
}

resource secretPlatformAdminEmails 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(platformAdminEmails)) {
  parent: vault
  name: 'platform-admin-emails'
  properties: {
    value: platformAdminEmails
  }
}

resource secretEntraAdminGroupId 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(entraAdminGroupId)) {
  parent: vault
  name: 'entra-admin-group-id'
  properties: {
    value: entraAdminGroupId
  }
}

// Placeholder secrets — required by SecretProviderClass, user must update post-deploy
resource secretEntraClientSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'entra-client-secret'
  properties: {
    value: 'PLACEHOLDER_UPDATE_AFTER_DEPLOY'
  }
}

resource secretJira 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'jira'
  properties: {
    value: 'PLACEHOLDER_UPDATE_AFTER_DEPLOY'
  }
}

// Platform secret key — used for JWT signing.  Auto-generated unique per deployment.
resource secretSecretKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'secret-key'
  properties: {
    value: uniqueString(vault.id, 'secret-key', resourceGroup().id)
  }
}

// Fernet encryption key — used for encrypting API keys at rest.
// Auto-generated unique per deployment.
resource secretEncryptionKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'encryption-key'
  properties: {
    value: uniqueString(vault.id, 'encryption-key', resourceGroup().id)
  }
}

// Placeholder secrets for MCP integrations (optional — user updates post-deploy)
resource secretGithubToken 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'github-token'
  properties: {
    value: 'PLACEHOLDER_UPDATE_AFTER_DEPLOY'
  }
}

resource secretSharepointTenantId 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'sharepoint-tenant-id'
  properties: {
    value: 'PLACEHOLDER_UPDATE_AFTER_DEPLOY'
  }
}

resource secretSharepointClientId 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'sharepoint-client-id'
  properties: {
    value: 'PLACEHOLDER_UPDATE_AFTER_DEPLOY'
  }
}

resource secretSharepointClientSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'sharepoint-client-secret'
  properties: {
    value: 'PLACEHOLDER_UPDATE_AFTER_DEPLOY'
  }
}

resource secretSharepointSiteHostname 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'sharepoint-site-hostname'
  properties: {
    value: 'PLACEHOLDER_UPDATE_AFTER_DEPLOY'
  }
}

// Azure AI Services secrets — auto-populated from provisioned AI account
resource aiServicesRef 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = if (!empty(aiServicesAccountName)) {
  name: aiServicesAccountName
}

resource secretAzureOpenAIEndpoint 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'azure-openai-endpoint'
  properties: {
    value: !empty(aiServicesEndpoint) ? aiServicesEndpoint : 'PLACEHOLDER_UPDATE_AFTER_DEPLOY'
  }
}

resource secretAzureOpenAIKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'azure-openai-key'
  properties: {
    value: !empty(aiServicesAccountName) ? aiServicesRef.listKeys().key1 : 'PLACEHOLDER_UPDATE_AFTER_DEPLOY'
  }
}

// Diagnostic settings — send audit logs to Log Analytics
resource keyvaultDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsWorkspaceId)) {
  name: 'keyvault-diagnostics'
  scope: vault
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'AuditEvent'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

@description('Resource ID of Key Vault')
output keyVaultId string = vault.id

@description('Name of Key Vault')
output keyVaultName string = vault.name

@description('URI of Key Vault')
output keyVaultUri string = vault.properties.vaultUri
