@description('Domain name for agent subdomains (e.g., agents.stumsft.com)')
param domainName string
@description('Tags')
param tags object = {}

resource dnsZone 'Microsoft.Network/dnsZones@2023-07-01-preview' = {
  name: domainName
  location: 'global'
  tags: tags
}

output dnsZoneId string = dnsZone.id
output dnsZoneName string = dnsZone.name
output nameServers array = dnsZone.properties.nameServers
