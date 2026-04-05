@description('Azure region for all resources')
param location string

@description('Environment name used in resource naming')
param environmentName string = 'prod'

@description('ACR SKU')
param sku string = 'Standard'

@description('Tags to apply to all resources')
param tags object = {}

// Azure Container Registry (names must be alphanumeric)
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: 'stumsftaiplatform${environmentName}acr'
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    adminUserEnabled: false
  }
}

@description('Resource ID of ACR')
output acrId string = acr.id

@description('ACR login server URL')
output acrLoginServer string = acr.properties.loginServer

@description('ACR name')
output acrName string = acr.name
