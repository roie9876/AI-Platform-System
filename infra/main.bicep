targetScope = 'resourceGroup'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Environment name — must be provided')
param environmentName string

@description('Number of AKS system node pool nodes')
param aksSystemNodeCount int = 2

@description('VM size for AKS system node pool')
param aksSystemNodeVmSize string = 'Standard_D4s_v5'

@description('Number of AKS user node pool nodes')
param aksUserNodeCount int = 1

@description('VM size for AKS user node pool')
param aksUserNodeVmSize string = 'Standard_D4s_v5'

@description('Kubernetes version')
param aksKubernetesVersion string = '1.33'

@description('ACR SKU tier')
param acrSku string = 'Standard'

@description('Log Analytics retention in days')
param logRetentionDays int = 30

@description('Email address for alert notifications')
param alertEmail string = 'admin@stumsft.com'

@description('Entra ID SPA application client ID (for user authentication)')
param entraAppClientId string

// Common tags applied to all resources
var commonTags = {
  SecurityControl: 'Ignore'
  Environment: environmentName
  Project: 'AI-Platform'
}

// ============================================================================
// Wave 1: No dependencies — leaf-node resources
// ============================================================================

module vnet './modules/vnet.bicep' = {
  name: 'vnet-deployment'
  params: {
    location: location
    environmentName: environmentName
    tags: commonTags
  }
}

module loganalytics './modules/loganalytics.bicep' = {
  name: 'loganalytics-deployment'
  params: {
    location: location
    environmentName: environmentName
    retentionInDays: logRetentionDays
    tags: commonTags
  }
}

module identity './modules/identity.bicep' = {
  name: 'identity-deployment'
  params: {
    location: location
    environmentName: environmentName
    tags: commonTags
  }
}

module cosmos './modules/cosmos.bicep' = {
  name: 'cosmos-deployment'
  params: {
    location: location
    environmentName: environmentName
    logAnalyticsWorkspaceId: loganalytics.outputs.workspaceId
    workloadIdentityPrincipalId: identity.outputs.workloadIdentityPrincipalId
    tags: commonTags
  }
}

// ============================================================================
// Wave 2: Depend on Wave 1 outputs
// ============================================================================

module acr './modules/acr.bicep' = {
  name: 'acr-deployment'
  params: {
    location: location
    environmentName: environmentName
    sku: acrSku
    aksIdentityPrincipalId: identity.outputs.aksIdentityPrincipalId
    tags: commonTags
  }
}

module aks './modules/aks.bicep' = {
  name: 'aks-deployment'
  params: {
    location: location
    environmentName: environmentName
    aksNodesSubnetId: vnet.outputs.aksNodesSubnetId
    aksPodsSubnetId: vnet.outputs.aksPodsSubnetId
    aksIdentityId: identity.outputs.aksIdentityId
    logAnalyticsWorkspaceId: loganalytics.outputs.workspaceId
    systemNodeCount: aksSystemNodeCount
    systemNodeVmSize: aksSystemNodeVmSize
    userNodeCount: aksUserNodeCount
    userNodeVmSize: aksUserNodeVmSize
    kubernetesVersion: aksKubernetesVersion
    tags: commonTags
  }
}

module keyvault './modules/keyvault.bicep' = {
  name: 'keyvault-deployment'
  params: {
    location: location
    environmentName: environmentName
    workloadIdentityPrincipalId: identity.outputs.workloadIdentityPrincipalId
    workloadIdentityClientId: identity.outputs.workloadIdentityClientId
    entraAppClientId: entraAppClientId
    cosmosEndpoint: cosmos.outputs.cosmosEndpoint
    logAnalyticsWorkspaceId: loganalytics.outputs.workspaceId
    tags: commonTags
  }
}

// ============================================================================
// Wave 3: Observability — depends on Log Analytics, AKS, Cosmos DB
// ============================================================================

module appInsights './modules/appinsights.bicep' = {
  name: 'appinsights-deployment'
  params: {
    location: location
    environmentName: environmentName
    workspaceId: loganalytics.outputs.workspaceId
    tags: commonTags
  }
}

module alerts './modules/alerts.bicep' = {
  name: 'alerts-deployment'
  params: {
    location: location
    environmentName: environmentName
    appInsightsId: appInsights.outputs.appInsightsId
    aksClusterId: aks.outputs.aksClusterId
    cosmosAccountId: cosmos.outputs.cosmosAccountId
    actionGroupEmail: alertEmail
    tags: commonTags
  }
}

module agc './modules/agc.bicep' = {
  name: 'agc-deployment'
  params: {
    location: location
    environmentName: environmentName
    agcSubnetId: vnet.outputs.agcSubnetId
    tags: commonTags
  }
}

// ============================================================================
// Wave 3.5: Workload Identity Federation — depends on identity + AKS OIDC issuer
// ============================================================================

resource workloadIdentityRef 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: 'stumsft-aiplatform-${environmentName}-workload-id'
}

resource federatedCredential 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: workloadIdentityRef
  name: 'aiplatform-federated-credential'
  properties: {
    issuer: aks.outputs.aksOidcIssuerUrl
    subject: 'system:serviceaccount:aiplatform:aiplatform-workload'
    audiences: [
      'api://AzureADTokenExchange'
    ]
  }
  dependsOn: [
    identity
  ]
}

// ============================================================================
// Outputs — key values from all modules for downstream consumption
// ============================================================================

@description('VNet resource ID')
output vnetId string = vnet.outputs.vnetId

@description('AKS cluster name')
output aksClusterName string = aks.outputs.aksClusterName

@description('AKS OIDC issuer URL for workload identity federation')
output aksOidcIssuerUrl string = aks.outputs.aksOidcIssuerUrl

@description('ACR login server URL')
output acrLoginServer string = acr.outputs.acrLoginServer

@description('Cosmos DB document endpoint')
output cosmosEndpoint string = cosmos.outputs.cosmosEndpoint

@description('Cosmos DB database name')
output cosmosDatabaseName string = cosmos.outputs.databaseName

@description('Key Vault URI')
output keyVaultUri string = keyvault.outputs.keyVaultUri

@description('Key Vault name')
output keyVaultName string = keyvault.outputs.keyVaultName

@description('Log Analytics workspace resource ID')
output logAnalyticsWorkspaceId string = loganalytics.outputs.workspaceId

@description('Workload identity client ID for pod identity binding')
output workloadIdentityClientId string = identity.outputs.workloadIdentityClientId

@description('Application Insights connection string')
output appInsightsConnectionString string = appInsights.outputs.connectionString

@description('Application Gateway for Containers resource ID')
output agcId string = agc.outputs.agcId
