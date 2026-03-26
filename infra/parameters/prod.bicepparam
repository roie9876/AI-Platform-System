using '../main.bicep'

param environmentName = 'prod'
param location = 'swedencentral'
param aksSystemNodeCount = 2
param aksSystemNodeVmSize = 'Standard_D4s_v5'
param aksUserNodeCount = 1
param aksUserNodeVmSize = 'Standard_D4s_v5'
param aksKubernetesVersion = '1.33'
param acrSku = 'Standard'
param logRetentionDays = 30
param alertEmail = 'admin@stumsft.com'
