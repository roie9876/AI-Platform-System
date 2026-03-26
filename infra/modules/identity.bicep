@description('Azure region for all resources')
param location string

@description('Environment name used in resource naming')
param environmentName string = 'prod'

// AKS control plane identity
resource aksIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'stumsft-aiplatform-${environmentName}-aks-id'
  location: location
}

// Workload identity for application pods
resource workloadIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'stumsft-aiplatform-${environmentName}-workload-id'
  location: location
}

@description('Resource ID of AKS control plane identity')
output aksIdentityId string = aksIdentity.id

@description('Principal ID of AKS control plane identity')
output aksIdentityPrincipalId string = aksIdentity.properties.principalId

@description('Resource ID of workload identity')
output workloadIdentityId string = workloadIdentity.id

@description('Principal ID of workload identity')
output workloadIdentityPrincipalId string = workloadIdentity.properties.principalId

@description('Client ID of workload identity')
output workloadIdentityClientId string = workloadIdentity.properties.clientId
