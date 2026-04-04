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
param entraAppClientId = '33aa4e94-7920-429e-ad78-bf7de0b89440'
param platformAdminEmails = 'aiadmin@MngEnvMCAP338326.onmicrosoft.com'
param entraAdminGroupId = '3f7be287-9368-4bd4-a628-1fa7bfe5580e'
param agentsDomain = ''
param buyDomain = false
param domainContactEmail = ''
param domainContactFirstName = ''
param domainContactLastName = ''
param domainContactPhone = ''
