@description('Azure region for the Service Bus namespace')
param location string

@description('Environment name for naming convention')
param environmentName string

@description('Log Analytics workspace ID for diagnostics')
param logAnalyticsWorkspaceId string

@description('Workload identity principal ID for RBAC')
param workloadIdentityPrincipalId string

@description('Object ID of the deployer principal for admin RBAC access')
param deployerPrincipalId string = ''

@description('Tags to apply to all resources')
param tags object

// Naming convention aligned with existing resources
var namePrefix = 'stumsft-aiplat-${environmentName}'
var namespaceName = '${namePrefix}-servicebus'

// Service Bus Namespace — Standard tier supports queues and KEDA triggers
resource sbNamespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: namespaceName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: false // KEDA needs SAS auth for queue triggers
  }
}

// Queue for agent execution requests — one shared queue, messages routed by agent_id label
resource agentRequestQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: sbNamespace
  name: 'agent-requests'
  properties: {
    lockDuration: 'PT5M'           // 5-min lock for long tool-calling loops
    maxSizeInMegabytes: 1024
    requiresDuplicateDetection: false
    defaultMessageTimeToLive: 'PT1H' // Messages expire after 1 hour
    deadLetteringOnMessageExpiration: true
    maxDeliveryCount: 3             // Retry 3 times before dead-lettering
    enablePartitioning: false
  }
}

// Queue for agent execution responses — clients poll or subscribe
resource agentResponseQueue 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = {
  parent: sbNamespace
  name: 'agent-responses'
  properties: {
    lockDuration: 'PT1M'
    maxSizeInMegabytes: 1024
    defaultMessageTimeToLive: 'PT1H'
    deadLetteringOnMessageExpiration: true
    maxDeliveryCount: 3
    enablePartitioning: false
  }
}

// SAS policy for KEDA to read queue metrics
resource kedaAuthRule 'Microsoft.ServiceBus/namespaces/AuthorizationRules@2022-10-01-preview' = {
  parent: sbNamespace
  name: 'keda-trigger'
  properties: {
    rights: [
      'Manage'
      'Listen'
      'Send'
    ]
  }
}

// RBAC: Azure Service Bus Data Owner for workload identity
resource sbDataOwnerRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sbNamespace.id, workloadIdentityPrincipalId, 'sbDataOwner')
  scope: sbNamespace
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '090c5cfd-751d-490a-894a-3ce6f1109419') // Azure Service Bus Data Owner
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// RBAC: Azure Service Bus Data Owner for deployer (admin can manage queues in portal)
resource sbDataOwnerDeployer 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(sbNamespace.id, deployerPrincipalId, 'sbDataOwnerDeployer')
  scope: sbNamespace
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '090c5cfd-751d-490a-894a-3ce6f1109419') // Azure Service Bus Data Owner
    principalId: deployerPrincipalId
    principalType: 'User'
  }
}

// Diagnostics → Log Analytics
resource sbDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'sb-diagnostics'
  scope: sbNamespace
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        categoryGroup: 'allLogs'
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

@description('Service Bus namespace fully qualified name')
output serviceBusNamespace string = '${sbNamespace.name}.servicebus.windows.net'

@description('Service Bus connection string for KEDA trigger auth')
output kedaConnectionString string = listKeys(kedaAuthRule.id, kedaAuthRule.apiVersion).primaryConnectionString

@description('Service Bus namespace resource ID')
output serviceBusId string = sbNamespace.id
