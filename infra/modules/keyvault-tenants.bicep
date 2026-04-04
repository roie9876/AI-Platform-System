@description('Azure region')
param location string
@description('Environment name')
param environmentName string = 'prod'
@description('Workload identity principal ID')
param workloadIdentityPrincipalId string
@description('Resource ID of Log Analytics workspace for diagnostics')
param logAnalyticsWorkspaceId string = ''
@description('Azure AD tenant ID')
param tenantId string = subscription().tenantId
@description('Tags')
param tags object = {}

resource tenantVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'stumsft-aiplat-${environmentName}-tkv'
  location: location
  tags: tags
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
    publicNetworkAccess: 'Enabled'
  }
}

resource kvSecretsUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(tenantVault.id, workloadIdentityPrincipalId, '4633458b-17de-408a-b874-0445c86b69e6')
  scope: tenantVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Diagnostic settings
resource tenantKvDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsWorkspaceId)) {
  name: 'tenant-kv-diagnostics'
  scope: tenantVault
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      { category: 'AuditEvent', enabled: true }
    ]
  }
}

output tenantKeyVaultName string = tenantVault.name
output tenantKeyVaultUri string = tenantVault.properties.vaultUri
