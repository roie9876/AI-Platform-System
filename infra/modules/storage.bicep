@description('Azure region')
param location string

@description('Environment name (e.g. dev, prod)')
param environmentName string

@description('Log Analytics workspace ID for diagnostics')
param logAnalyticsWorkspaceId string

@description('Workload Identity principal ID for RBAC')
param workloadIdentityPrincipalId string

@description('Tags to apply to all resources')
param tags object = {}

// Naming: stumsft-aiplat-{env}-storage (max 24 chars for storage accounts)
var storageName = replace('stumsftaiplat${environmentName}st', '-', '')

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    defaultToOAuthAuthentication: true
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 30
    }
  }
}

// Container for archived agent session data
resource archiveContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'agent-archives'
  properties: {
    publicAccess: 'None'
  }
}

// Storage Blob Data Contributor for workload identity (archive writes)
var storageBlobDataContributorRole = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'

resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, workloadIdentityPrincipalId, storageBlobDataContributorRole)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributorRole)
    principalId: workloadIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Diagnostics
resource diagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: blobService
  name: '${storageName}-diag'
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
        category: 'Transaction'
        enabled: true
      }
    ]
  }
}

@description('Storage account name')
output storageAccountName string = storageAccount.name

@description('Blob endpoint URL')
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob
