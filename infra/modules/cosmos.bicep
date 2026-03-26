@description('Azure region for all resources')
param location string

@description('Environment name used in resource naming')
param environmentName string = 'prod'

@description('Resource ID of Log Analytics workspace for diagnostics (optional)')
param logAnalyticsWorkspaceId string = ''

// Cosmos DB Account - Serverless NoSQL
resource account 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: 'stumsft-aiplatform-${environmentName}-cosmos'
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
      }
    ]
    publicNetworkAccess: 'Enabled'
  }
}

// Database
resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: account
  name: 'aiplatform'
  properties: {
    resource: {
      id: 'aiplatform'
    }
  }
}

// Containers requiring uniqueKeyPolicy for business uniqueness within a partition.
// NOTE: Cosmos DB uniqueKeyPolicy is immutable after container creation.
// Existing containers require recreation to add unique keys.
var containersWithUniqueKeys = [
  { name: 'agents', uniqueKeyPaths: ['/slug'] }
  { name: 'data_sources', uniqueKeyPaths: ['/name'] }
  { name: 'mcp_servers', uniqueKeyPaths: ['/name'] }
  { name: 'model_endpoints', uniqueKeyPaths: ['/name'] }
  { name: 'tenants', uniqueKeyPaths: ['/slug'] }
  { name: 'tools', uniqueKeyPaths: ['/name'] }
  { name: 'users', uniqueKeyPaths: ['/email'] }
]

// All remaining containers without unique key constraints
var simpleContainerNames = [
  'agent_config_versions'
  'agent_data_sources'
  'agent_mcp_tools'
  'agent_memories'
  'agent_templates'
  'agent_tools'
  'azure_connections'
  'azure_subscriptions'
  'catalog_entries'
  'cost_alerts'
  'documents'
  'document_chunks'
  'evaluation_results'
  'evaluation_runs'
  'execution_logs'
  'mcp_discovered_tools'
  'model_pricing'
  'refresh_tokens'
  'test_cases'
  'test_suites'
  'thread_messages'
  'threads'
  'tool_templates'
  'workflow_edges'
  'workflow_executions'
  'workflow_node_executions'
  'workflow_nodes'
  'workflows'
]

// Create containers with uniqueKeyPolicy
resource uniqueContainers 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = [for container in containersWithUniqueKeys: {
  parent: database
  name: container.name
  properties: {
    resource: {
      id: container.name
      partitionKey: {
        paths: [
          '/tenant_id'
        ]
        kind: 'Hash'
      }
      uniqueKeyPolicy: {
        uniqueKeys: [
          {
            paths: container.uniqueKeyPaths
          }
        ]
      }
    }
  }
}]

// Create remaining containers with /tenant_id partition key (no unique keys)
resource simpleContainers 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = [for name in simpleContainerNames: {
  parent: database
  name: name
  properties: {
    resource: {
      id: name
      partitionKey: {
        paths: [
          '/tenant_id'
        ]
        kind: 'Hash'
      }
    }
  }
}]

// Diagnostic settings — send logs to Log Analytics
resource cosmosDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsWorkspaceId)) {
  name: 'cosmos-diagnostics'
  scope: account
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        category: 'DataPlaneRequests'
        enabled: true
      }
      {
        category: 'QueryRuntimeStatistics'
        enabled: true
      }
      {
        category: 'PartitionKeyStatistics'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'Requests'
        enabled: true
      }
    ]
  }
}

@description('Resource ID of the Cosmos DB account')
output cosmosAccountId string = account.id

@description('Name of the Cosmos DB account')
output cosmosAccountName string = account.name

@description('Document endpoint of the Cosmos DB account')
output cosmosEndpoint string = account.properties.documentEndpoint

@description('Name of the database')
output databaseName string = 'aiplatform'
