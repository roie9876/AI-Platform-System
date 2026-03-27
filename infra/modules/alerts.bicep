@description('Azure region for all resources')
param location string

@description('Environment name used in resource naming')
param environmentName string = 'prod'

@description('Resource ID of Application Insights')
param appInsightsId string

@description('Resource ID of AKS cluster')
param aksClusterId string

@description('Resource ID of Cosmos DB account')
param cosmosAccountId string

@description('Email address for alert notifications')
param actionGroupEmail string = 'admin@stumsft.com'

@description('Tags to apply to all resources')
param tags object = {}

// Action Group
resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'stumsft-aiplatform-${environmentName}-ag'
  location: 'global'
  tags: tags
  properties: {
    groupShortName: 'AIPlatform'
    enabled: true
    emailReceivers: [
      {
        name: 'PlatformAdmin'
        emailAddress: actionGroupEmail
        useCommonAlertSchema: true
      }
    ]
  }
}

// Alert: AKS pod restart count > 5 in 5 min
resource podRestartAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'stumsft-aiplatform-${environmentName}-aks-pod-restart-alert'
  location: 'global'
  tags: tags
  properties: {
    description: 'AKS pod restart count exceeds threshold'
    severity: 2
    enabled: true
    scopes: [aksClusterId]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    autoMitigate: true
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'PodRestarts'
          metricName: 'restartingContainerCount'
          metricNamespace: 'Insights.Container/pods'
          operator: 'GreaterThan'
          threshold: 5
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// Alert: Application Insights 5xx rate > 10 in 5 min
resource fiveXXAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'stumsft-aiplatform-${environmentName}-app-5xx-rate-alert'
  location: 'global'
  tags: tags
  properties: {
    description: 'Application 5xx error rate exceeds threshold'
    severity: 2
    enabled: true
    scopes: [appInsightsId]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    autoMitigate: true
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'FailedRequests'
          metricName: 'requests/failed'
          metricNamespace: 'microsoft.insights/components'
          operator: 'GreaterThan'
          threshold: 10
          timeAggregation: 'Count'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// Alert: Cosmos DB Normalized RU Consumption > 80%
resource cosmosRUAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'stumsft-aiplatform-${environmentName}-cosmos-ru-consumption-alert'
  location: 'global'
  tags: tags
  properties: {
    description: 'Cosmos DB Normalized RU Consumption exceeds 80%'
    severity: 2
    enabled: true
    scopes: [cosmosAccountId]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    autoMitigate: true
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'NormalizedRU'
          metricName: 'NormalizedRUConsumption'
          metricNamespace: 'microsoft.documentdb/databaseaccounts'
          operator: 'GreaterThan'
          threshold: 80
          timeAggregation: 'Maximum'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

// Alert: AKS node CPU > 80%
resource nodeCPUAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'stumsft-aiplatform-${environmentName}-aks-node-cpu-alert'
  location: 'global'
  tags: tags
  properties: {
    description: 'AKS node CPU usage exceeds 80%'
    severity: 2
    enabled: true
    scopes: [aksClusterId]
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    autoMitigate: true
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'NodeCPU'
          metricName: 'node_cpu_usage_percentage'
          metricNamespace: 'Insights.Container/nodes'
          operator: 'GreaterThan'
          threshold: 80
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}
