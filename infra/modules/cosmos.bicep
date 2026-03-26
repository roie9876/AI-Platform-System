@description('Azure region for all resources')
param location string

@description('Environment name used in resource naming')
param environmentName string = 'prod'

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

// All container names mapped from existing SQLAlchemy __tablename__ values
var containerNames = [
  'agents'
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
  'data_sources'
  'documents'
  'document_chunks'
  'evaluation_results'
  'evaluation_runs'
  'execution_logs'
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

@description('Resource ID of the Cosmos DB account')
output cosmosAccountId string = account.id

@description('Name of the Cosmos DB account')
output cosmosAccountName string = account.name

@description('Document endpoint of the Cosmos DB account')
output cosmosEndpoint string = account.properties.documentEndpoint

@description('Name of the database')
output databaseName string = 'aiplatform'
