@description('Azure region for all resources')
param location string

@description('Environment name used in resource naming')
param environmentName string = 'prod'

@description('Resource ID of Log Analytics workspace')
param workspaceId string

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'stumsft-aiplatform-${environmentName}-appi'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspaceId
    IngestionMode: 'LogAnalytics'
    RetentionInDays: 90
  }
}

@description('Resource ID of Application Insights')
output appInsightsId string = appInsights.id

@description('Instrumentation key')
output instrumentationKey string = appInsights.properties.InstrumentationKey

@description('Connection string for Application Insights')
output connectionString string = appInsights.properties.ConnectionString
