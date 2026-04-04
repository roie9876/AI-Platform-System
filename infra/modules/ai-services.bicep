@description('Azure region for all resources')
param location string

@description('Environment name used in resource naming')
param environmentName string = 'prod'

@description('Resource ID of Log Analytics workspace for diagnostics')
param logAnalyticsWorkspaceId string = ''

@description('Principal ID of workload identity for Cognitive Services RBAC')
param workloadIdentityPrincipalId string

@description('Object ID of the deployer principal for admin RBAC access')
param deployerPrincipalId string = ''

@description('Embedding model to deploy (platform-level, shared across tenants)')
param embeddingModelName string = 'text-embedding-3-large'

@description('Embedding model version')
param embeddingModelVersion string = '1'

@description('Embedding model TPM capacity (in thousands)')
param embeddingModelCapacity int = 120

@description('Tags to apply to all resources')
param tags object = {}

// ============================================================================
// Azure AI Services account (multi-model: OpenAI, embeddings, etc.)
// ============================================================================

var accountName = 'stumsft-aiplat-${environmentName}-ai'

resource aiAccount 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: accountName
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false
  }
}

// ============================================================================
// Default embedding model deployment (platform-level, shared across tenants)
// ============================================================================

resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiAccount
  name: embeddingModelName
  sku: {
    name: 'Standard'
    capacity: embeddingModelCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModelName
      version: embeddingModelVersion
    }
  }
}

// ============================================================================
// RBAC: Workload identity — Cognitive Services OpenAI User (invoke models)
// ============================================================================

resource openAIUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiAccount.id, workloadIdentityPrincipalId, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  scope: aiAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd') // Cognitive Services OpenAI User
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// RBAC: Deployer — Cognitive Services OpenAI Contributor (manage deployments)
// ============================================================================

resource openAIContributorDeployer 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(aiAccount.id, deployerPrincipalId, 'a001fd3d-188f-4b5d-821b-7da978bf7442')
  scope: aiAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a001fd3d-188f-4b5d-821b-7da978bf7442') // Cognitive Services OpenAI Contributor
    principalId: deployerPrincipalId
    principalType: 'User'
  }
}

// ============================================================================
// RBAC: Workload identity — Cognitive Services OpenAI Contributor
// (needed for backend to create/manage model deployments via API)
// ============================================================================

resource openAIContributorWorkload 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(aiAccount.id, workloadIdentityPrincipalId, 'a001fd3d-188f-4b5d-821b-7da978bf7442')
  scope: aiAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a001fd3d-188f-4b5d-821b-7da978bf7442') // Cognitive Services OpenAI Contributor
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ============================================================================
// Diagnostics
// ============================================================================

resource aiDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsWorkspaceId)) {
  name: 'ai-diagnostics'
  scope: aiAccount
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'Audit'
        enabled: true
      }
      {
        category: 'RequestResponse'
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

// ============================================================================
// Outputs
// ============================================================================

@description('Azure AI Services endpoint')
output aiEndpoint string = aiAccount.properties.endpoint

@description('Azure AI Services account name')
output aiAccountName string = aiAccount.name

@description('Azure AI Services account resource ID')
output aiAccountId string = aiAccount.id
