@description('Azure region for all resources')
param location string

@description('Environment name used in resource naming')
param environmentName string = 'prod'

@description('VNet address space')
param vnetAddressPrefix string = '10.0.0.0/16'

@description('AKS nodes subnet address prefix')
param aksNodesSubnetPrefix string = '10.0.0.0/22'

@description('AKS pods subnet address prefix (Azure CNI Overlay)')
param aksPodsSubnetPrefix string = '10.0.4.0/22'

@description('Private endpoints subnet address prefix')
param privateEndpointsSubnetPrefix string = '10.0.8.0/24'

// NSG for aks-nodes subnet
resource aksNodesNsg 'Microsoft.Network/networkSecurityGroups@2024-01-01' = {
  name: 'stumsft-aiplatform-${environmentName}-nsg-aks-nodes'
  location: location
  properties: {
    securityRules: [
      {
        name: 'DenyAllInbound'
        properties: {
          priority: 4096
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'AllowAllOutbound'
        properties: {
          priority: 4096
          direction: 'Outbound'
          access: 'Allow'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

// NSG for aks-pods subnet
resource aksPodsNsg 'Microsoft.Network/networkSecurityGroups@2024-01-01' = {
  name: 'stumsft-aiplatform-${environmentName}-nsg-aks-pods'
  location: location
  properties: {
    securityRules: [
      {
        name: 'DenyAllInbound'
        properties: {
          priority: 4096
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'AllowAllOutbound'
        properties: {
          priority: 4096
          direction: 'Outbound'
          access: 'Allow'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

// NSG for private-endpoints subnet
resource privateEndpointsNsg 'Microsoft.Network/networkSecurityGroups@2024-01-01' = {
  name: 'stumsft-aiplatform-${environmentName}-nsg-private-endpoints'
  location: location
  properties: {
    securityRules: [
      {
        name: 'DenyAllInbound'
        properties: {
          priority: 4096
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'AllowAllOutbound'
        properties: {
          priority: 4096
          direction: 'Outbound'
          access: 'Allow'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: '*'
          destinationAddressPrefix: '*'
        }
      }
    ]
  }
}

// Virtual Network with 3 subnets
resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: 'stumsft-aiplatform-${environmentName}-vnet'
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    subnets: [
      {
        name: 'aks-nodes'
        properties: {
          addressPrefix: aksNodesSubnetPrefix
          networkSecurityGroup: {
            id: aksNodesNsg.id
          }
        }
      }
      {
        name: 'aks-pods'
        properties: {
          addressPrefix: aksPodsSubnetPrefix
          networkSecurityGroup: {
            id: aksPodsNsg.id
          }
        }
      }
      {
        name: 'private-endpoints'
        properties: {
          addressPrefix: privateEndpointsSubnetPrefix
          networkSecurityGroup: {
            id: privateEndpointsNsg.id
          }
        }
      }
    ]
  }
}

@description('Resource ID of the VNet')
output vnetId string = vnet.id

@description('Name of the VNet')
output vnetName string = vnet.name

@description('Resource ID of the aks-nodes subnet')
output aksNodesSubnetId string = vnet.properties.subnets[0].id

@description('Resource ID of the aks-pods subnet')
output aksPodsSubnetId string = vnet.properties.subnets[1].id

@description('Resource ID of the private-endpoints subnet')
output privateEndpointsSubnetId string = vnet.properties.subnets[2].id
