@description('ACR resource name')
param acrName string

@description('Principal ID of AKS kubelet identity for AcrPull role assignment')
param kubeletIdentityObjectId string

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: acrName
}

resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, kubeletIdentityObjectId, '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d') // AcrPull
    principalId: kubeletIdentityObjectId
    principalType: 'ServicePrincipal'
  }
}
