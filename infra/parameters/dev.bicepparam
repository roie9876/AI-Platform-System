using '../main.bicep'

param environmentName = 'dev'
param location = 'swedencentral'
param aksSystemNodeCount = 1
param aksSystemNodeVmSize = 'Standard_D2s_v5'
param aksUserNodeCount = 1
param aksUserNodeVmSize = 'Standard_D2s_v5'
param aksKubernetesVersion = '1.33'
param acrSku = 'Standard'
param logRetentionDays = 30
param alertEmail = 'admin@stumsft.com'
// App Registration is auto-created by preprovision.sh if left empty.
// Set this to skip auto-creation and use an existing App Registration.
param entraAppClientId = ''
param platformAdminEmails = 'aiadmin@MngEnvMCAP338326.onmicrosoft.com'
param entraAdminGroupId = '3f7be287-9368-4bd4-a628-1fa7bfe5580e'
param agentsDomain = ''
param buyDomain = false
param domainContactEmail = ''
param domainContactFirstName = ''
param domainContactLastName = ''
param domainContactPhone = ''
