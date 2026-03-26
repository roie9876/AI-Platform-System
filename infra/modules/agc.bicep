@description('Azure region for all resources')
param location string

@description('Environment name used in resource naming')
param environmentName string = 'prod'

@description('Resource ID of the AGC subnet (must have Microsoft.ServiceNetworking delegation)')
param agcSubnetId string

// Application Gateway for Containers (Traffic Controller)
resource trafficController 'Microsoft.ServiceNetworking/trafficControllers@2025-01-01' = {
  name: 'stumsft-aiplatform-${environmentName}-agc'
  location: location
  properties: {}
}

// Association — links the AGC to the delegated subnet
resource association 'Microsoft.ServiceNetworking/trafficControllers/associations@2025-01-01' = {
  parent: trafficController
  name: 'agc-subnet-association'
  location: location
  properties: {
    associationType: 'subnets'
    subnet: {
      id: agcSubnetId
    }
  }
}

// Frontend — creates the public-facing entry point with a managed FQDN
resource frontend 'Microsoft.ServiceNetworking/trafficControllers/frontends@2025-01-01' = {
  parent: trafficController
  name: 'agc-frontend'
  location: location
  properties: {}
}

@description('Resource ID of the Application Gateway for Containers')
output agcId string = trafficController.id

@description('Name of the Application Gateway for Containers')
output agcName string = trafficController.name

@description('FQDN of the AGC frontend')
output agcFqdn string = frontend.properties.fqdn
