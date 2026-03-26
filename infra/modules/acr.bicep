@description('Azure region for all resources')
param location string

@description('Environment name used in resource naming')
param environmentName string = 'prod'

@description('ACR SKU')
param sku string = 'Standard'

@description('Principal ID of AKS identity for AcrPull role assignment')
param aksIdentityPrincipalId string

// Azure Container Registry (names must be alphanumeric)
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'stumsftaiplatform${environmentName}acr'
  location: location
  sku: {
    name: sku
  }
  properties: {
    adminUserEnabled: false
  }
}

// AcrPull role assignment for AKS identity
resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, aksIdentityPrincipalId, '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: aksIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

@description('Resource ID of ACR')
output acrId string = acr.id

@description('ACR login server URL')
output acrLoginServer string = acr.properties.loginServer

@description('ACR name')
output acrName string = acr.name
