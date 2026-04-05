@description('Azure region for all resources')
param location string

@description('Environment name used in resource naming')
param environmentName string = 'prod'

@description('AKS nodes subnet resource ID')
param aksNodesSubnetId string

@description('AKS pods subnet resource ID (for CNI Overlay pod subnet)')
param aksPodsSubnetId string

@description('Resource ID of AKS control plane user-assigned identity')
param aksIdentityId string

@description('Resource ID of Log Analytics workspace for monitoring')
param logAnalyticsWorkspaceId string

@description('Number of system node pool nodes')
param systemNodeCount int = 2

@description('VM size for system node pool')
param systemNodeVmSize string = 'Standard_D4s_v5'

@description('Number of user node pool nodes')
param userNodeCount int = 1

@description('VM size for user node pool')
param userNodeVmSize string = 'Standard_D4s_v5'

@description('Enable cluster autoscaler for user node pool')
param enableAutoScaling bool = true

@description('Minimum node count for user pool autoscaler')
param userNodeMinCount int = 1

@description('Maximum node count for user pool autoscaler')
param userNodeMaxCount int = 5

@description('Object ID of the deployer principal for AKS RBAC Cluster Admin')
param deployerPrincipalId string = ''

@description('Kubernetes version')
param kubernetesVersion string = '1.33'

@description('Tags to apply to all resources')
param tags object = {}

resource cluster 'Microsoft.ContainerService/managedClusters@2024-05-01' = {
  name: 'stumsft-aiplatform-${environmentName}-aks'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${aksIdentityId}': {}
    }
  }
  properties: {
    kubernetesVersion: kubernetesVersion
    dnsPrefix: 'stumsft-aiplatform-${environmentName}'
    enableRBAC: true
    aadProfile: {
      managed: true
      enableAzureRBAC: true
    }
    networkProfile: {
      networkPlugin: 'azure'
      networkPluginMode: 'overlay'
      podCidr: '192.168.0.0/16'
      serviceCidr: '172.16.0.0/16'
      dnsServiceIP: '172.16.0.10'
    }
    addonProfiles: {
      omsagent: {
        enabled: true
        config: {
          logAnalyticsWorkspaceResourceID: logAnalyticsWorkspaceId
        }
      }
      azureKeyvaultSecretsProvider: {
        enabled: true
        config: {
          enableSecretRotation: 'true'
          rotationPollInterval: '2m'
        }
      }
    }
    oidcIssuerProfile: {
      enabled: true
    }
    securityProfile: {
      workloadIdentity: {
        enabled: true
      }
    }
    agentPoolProfiles: [
      {
        name: 'system'
        mode: 'System'
        count: systemNodeCount
        vmSize: systemNodeVmSize
        vnetSubnetID: aksNodesSubnetId
        osType: 'Linux'
        osDiskSizeGB: 128
        enableAutoScaling: enableAutoScaling
        minCount: enableAutoScaling ? 1 : null
        maxCount: enableAutoScaling ? 3 : null
      }
      {
        name: 'userpool'
        mode: 'User'
        count: userNodeCount
        vmSize: userNodeVmSize
        vnetSubnetID: aksNodesSubnetId
        osType: 'Linux'
        osDiskSizeGB: 128
        enableAutoScaling: enableAutoScaling
        minCount: enableAutoScaling ? userNodeMinCount : null
        maxCount: enableAutoScaling ? userNodeMaxCount : null
      }
    ]
  }
}

// AKS RBAC Cluster Admin for deployer (Azure AD RBAC enabled cluster)
resource aksRbacClusterAdminDeployer 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerPrincipalId)) {
  name: guid(cluster.id, deployerPrincipalId, 'b1ff04bb-8a4e-4dc4-8eb5-8693973ce19b')
  scope: cluster
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b1ff04bb-8a4e-4dc4-8eb5-8693973ce19b') // Azure Kubernetes Service RBAC Cluster Admin
    principalId: deployerPrincipalId
    principalType: 'User'
  }
}

@description('Resource ID of the AKS cluster')
output aksClusterId string = cluster.id

@description('Name of the AKS cluster')
output aksClusterName string = cluster.name

@description('OIDC issuer URL for workload identity federation')
output aksOidcIssuerUrl string = cluster.properties.oidcIssuerProfile.issuerURL

@description('Principal ID of the kubelet managed identity (used for ACR pull)')
output aksKubeletIdentityObjectId string = cluster.properties.identityProfile.kubeletidentity.objectId
