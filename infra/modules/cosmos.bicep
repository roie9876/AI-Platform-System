@description('Azure region for all resources')
param location string

@description('Environment name used in resource naming')
param environmentName string = 'prod'

@description('Resource ID of Log Analytics workspace for diagnostics (optional)')
param logAnalyticsWorkspaceId string = ''

@description('Principal ID of workload identity for Cosmos DB data plane RBAC')
param workloadIdentityPrincipalId string

@description('Object ID of the deployer principal for admin RBAC access')
param deployerPrincipalId string = ''

@description('Tags to apply to all resources')
param tags object = {}

// Cosmos DB Account - Serverless NoSQL
resource account 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: 'stumsft-aiplatform-${environmentName}-cosmos'
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    capabilities: [
      {
        name: 'EnableServerless'
      }
      {
        name: 'EnableNoSQLVectorSearch'
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
// These containers were originally created without unique keys and cannot
// be modified via Bicep. Unique key enforcement is handled at the application layer.
// To add unique keys, containers must be manually dropped and recreated.

// All containers with /tenant_id partition key
var containerNames = [
  'agents'
  'agent_config_versions'
  'agent_data_sources'
  'agent_mcp_tools'
  'agent_templates'
  'agent_tools'
  'azure_connections'
  'azure_subscriptions'
  'catalog_entries'
  'cost_alerts'
  'data_sources'
  'documents'
  'document_chunks'
  'evaluation_results'
  'evaluation_runs'
  'execution_logs'
  'execution_results'
  'mcp_discovered_tools'
  'mcp_servers'
  'model_endpoints'
  'model_pricing'
  'refresh_tokens'
  'tenants'
  'test_cases'
  'test_suites'
  'thread_messages'
  'threads'
  'tool_templates'
  'tools'
  'users'
  'workflow_edges'
  'workflow_executions'
  'workflow_node_executions'
  'workflow_nodes'
  'workflows'
]

// Create all containers with /tenant_id partition key
resource containers 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = [for name in containerNames: {
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

// token_logs container — 90-day TTL, partition by tenant_id (Phase 29: Token Proxy)
resource tokenLogsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'token_logs'
  properties: {
    resource: {
      id: 'token_logs'
      partitionKey: {
        paths: ['/tenant_id']
        kind: 'Hash'
      }
      defaultTtl: 7776000  // 90 days in seconds
    }
  }
}

// agent_memories container — with DiskANN vector embedding policy (Phase 30: MCP Servers)
resource agentMemoriesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'agent_memories'
  properties: {
    resource: {
      id: 'agent_memories'
      partitionKey: {
        paths: ['/tenant_id']
        kind: 'Hash'
      }
      vectorEmbeddingPolicy: {
        vectorEmbeddings: [
          {
            path: '/embedding'
            dataType: 'float32'
            dimensions: 1536
            distanceFunction: 'cosine'
          }
        ]
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [{ path: '/*' }]
        excludedPaths: [
          { path: '/_etag/?' }
          { path: '/embedding/*' }
        ]
        vectorIndexes: [
          {
            path: '/embedding'
            type: 'diskANN'
          }
        ]
      }
    }
  }
}

// memory_query_cache container — TTL-based cache for embedding lookups (Phase 30: MCP Servers)
resource memoryQueryCacheContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'memory_query_cache'
  properties: {
    resource: {
      id: 'memory_query_cache'
      partitionKey: {
        paths: ['/tenant_id']
        kind: 'Hash'
      }
      defaultTtl: 3600
    }
  }
}

// structured_memories container — key-value facts without embeddings (Phase 30: MCP Servers)
resource structuredMemoriesContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'structured_memories'
  properties: {
    resource: {
      id: 'structured_memories'
      partitionKey: {
        paths: ['/tenant_id']
        kind: 'Hash'
      }
    }
  }
}

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

// Cosmos DB Built-in Data Contributor role assignment for workload identity
// Role ID 00000000-0000-0000-0000-000000000002 = Built-in Data Contributor (read/write all data)
resource cosmosDataContributorRole 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: account
  name: guid(account.id, workloadIdentityPrincipalId, '00000000-0000-0000-0000-000000000002')
  properties: {
    roleDefinitionId: '${account.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: workloadIdentityPrincipalId
    scope: account.id
  }
}

// Cosmos DB Built-in Data Contributor role for deployer (admin can read/write data in portal & Data Explorer)
resource cosmosDataContributorDeployer 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = if (!empty(deployerPrincipalId)) {
  parent: account
  name: guid(account.id, deployerPrincipalId, '00000000-0000-0000-0000-000000000002')
  properties: {
    roleDefinitionId: '${account.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    principalId: deployerPrincipalId
    scope: account.id
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
