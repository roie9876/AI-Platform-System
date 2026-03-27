@description('Azure region for all resources')
param location string

@description('Environment name used in resource naming')
param environmentName string = 'prod'

@description('Log retention in days')
param retentionInDays int = 30

@description('Tags to apply to all resources')
param tags object = {}

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'stumsft-aiplatform-${environmentName}-law'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: retentionInDays
  }
}

@description('Resource ID of the Log Analytics workspace')
output workspaceId string = workspace.id

@description('Name of the Log Analytics workspace')
output workspaceName string = workspace.name

@description('Customer ID of the Log Analytics workspace')
output workspaceCustomerId string = workspace.properties.customerId
