@description('Azure region for all resources')
param location string

@description('Environment name used in resource naming')
param environmentName string = 'prod'

@description('Principal ID of workload identity for Key Vault Secrets User role')
param workloadIdentityPrincipalId string

@description('Resource ID of Log Analytics workspace for diagnostics (optional)')
param logAnalyticsWorkspaceId string = ''

@description('Azure AD tenant ID')
param tenantId string = subscription().tenantId

// Key Vault name max 24 chars: stumsft-aiplat-prod-kv = 22 chars
resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'stumsft-aiplat-${environmentName}-kv'
  location: location
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
