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
param alertEmail = 'roie.ben@microsoft.com'
// App Registration is auto-created by preprovision.sh if left empty.
// Set this to skip auto-creation and use an existing App Registration.
param entraAppClientId = '71f438b4-6272-4f4c-b444-49e88df6394a'
param platformAdminEmails = 'aiadmin@MngEnvMCAP338326.onmicrosoft.com'
param entraAdminGroupId = '3f7be287-9368-4bd4-a628-1fa7bfe5580e'
param agentsDomain = ''
param buyDomain = false
param domainContactEmail = ''
param domainContactFirstName = ''
param domainContactLastName = ''
param domainContactPhone = ''
