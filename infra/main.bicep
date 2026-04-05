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
param entraAppClientId string = ''

@description('Platform admin email addresses (comma-separated)')
param platformAdminEmails string = ''

@description('Entra admin group ID for platform admins')
param entraAdminGroupId string = ''

@description('Custom domain for agent subdomains. Leave empty for AGC-managed FQDN only.')
param agentsDomain string = ''

@description('Whether to purchase the domain via App Service Domains. Only used when agentsDomain is set.')
param buyDomain bool = false

@description('ICANN contact email for domain purchase. Required when buyDomain is true.')
param domainContactEmail string = ''

@description('ICANN contact first name for domain purchase.')
param domainContactFirstName string = ''

@description('ICANN contact last name for domain purchase.')
param domainContactLastName string = ''

@description('ICANN contact phone for domain purchase.')
param domainContactPhone string = ''

@description('Object ID of the deployer (admin) principal — auto-set by preprovision.sh for data-plane RBAC on Key Vault, Cosmos DB, etc.')
param deployerPrincipalId string = ''

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
    deployerPrincipalId: deployerPrincipalId
    tags: commonTags
  }
}

module aiServices './modules/ai-services.bicep' = {
  name: 'ai-services-deployment'
  params: {
    location: location
    environmentName: environmentName
    logAnalyticsWorkspaceId: loganalytics.outputs.workspaceId
    workloadIdentityPrincipalId: identity.outputs.workloadIdentityPrincipalId
    deployerPrincipalId: deployerPrincipalId
    tags: commonTags
  }
}

module dnsZone './modules/dns.bicep' = if (!empty(agentsDomain)) {
  name: 'dns-deployment'
  params: {
    domainName: agentsDomain
    tags: commonTags
  }
}

module domain './modules/domain.bicep' = if (buyDomain && !empty(agentsDomain)) {
  name: 'domain-deployment'
  params: {
    domainName: agentsDomain
    contactEmail: domainContactEmail
    contactFirstName: domainContactFirstName
    contactLastName: domainContactLastName
    contactPhone: domainContactPhone
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
    deployerPrincipalId: deployerPrincipalId
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

module servicebus './modules/servicebus.bicep' = {
  name: 'servicebus-deployment'
  params: {
    location: location
    environmentName: environmentName
    logAnalyticsWorkspaceId: loganalytics.outputs.workspaceId
    workloadIdentityPrincipalId: identity.outputs.workloadIdentityPrincipalId
    deployerPrincipalId: deployerPrincipalId
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
// Wave 4: Key Vault — depends on Wave 3 outputs (App Insights, Service Bus)
// ============================================================================

module keyvault './modules/keyvault.bicep' = {
  name: 'keyvault-deployment'
  params: {
    location: location
    environmentName: environmentName
    workloadIdentityPrincipalId: identity.outputs.workloadIdentityPrincipalId
    workloadIdentityClientId: identity.outputs.workloadIdentityClientId
    entraAppClientId: entraAppClientId
    cosmosEndpoint: cosmos.outputs.cosmosEndpoint
    serviceBusNamespace: servicebus.outputs.serviceBusNamespace
    appInsightsConnectionString: appInsights.outputs.connectionString
    platformAdminEmails: platformAdminEmails
    entraAdminGroupId: entraAdminGroupId
    logAnalyticsWorkspaceId: loganalytics.outputs.workspaceId
    deployerPrincipalId: deployerPrincipalId
    aiServicesEndpoint: aiServices.outputs.aiEndpoint
    aiServicesAccountName: aiServices.outputs.aiAccountName
    tags: commonTags
  }
}

module keyvaultTenants './modules/keyvault-tenants.bicep' = {
  name: 'keyvault-tenants-deployment'
  params: {
    location: location
    environmentName: environmentName
    workloadIdentityPrincipalId: identity.outputs.workloadIdentityPrincipalId
    logAnalyticsWorkspaceId: loganalytics.outputs.workspaceId
    deployerPrincipalId: deployerPrincipalId
    tags: commonTags
  }
}

// ============================================================================
// Wave 4.5: Workload Identity Federation — depends on identity + AKS OIDC issuer
// ============================================================================

resource workloadIdentityRef 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = {
  name: 'stumsft-aiplatform-${environmentName}-workload-id'
}

resource federatedCredential 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: workloadIdentityRef
  name: 'aiplatform-workload-fed'
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

@description('Service Bus namespace FQDN')
output serviceBusNamespace string = servicebus.outputs.serviceBusNamespace

@description('Tenant Key Vault name')
output tenantKeyVaultName string = keyvaultTenants.outputs.tenantKeyVaultName

@description('Tenant Key Vault URI')
output tenantKeyVaultUri string = keyvaultTenants.outputs.tenantKeyVaultUri

@description('DNS zone name servers (empty if no custom domain)')
output dnsNameServers array = !empty(agentsDomain) ? dnsZone.outputs.nameServers : []

@description('Custom agents domain (empty if not configured)')
output agentsDomain string = agentsDomain

@description('Azure AI Services endpoint')
output aiServicesEndpoint string = aiServices.outputs.aiEndpoint

@description('Azure AI Services account name')
output aiServicesAccountName string = aiServices.outputs.aiAccountName
