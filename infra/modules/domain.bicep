@description('Domain name to purchase')
param domainName string
@description('Contact info for ICANN registration')
param contactEmail string
param contactFirstName string
param contactLastName string
param contactPhone string
@description('Tags')
param tags object = {}

@description('UTC timestamp for ICANN consent (auto-populated)')
param consentTimestamp string = utcNow()

resource appServiceDomain 'Microsoft.DomainRegistration/domains@2024-04-01' = {
  name: domainName
  location: 'global'
  tags: tags
  properties: {
    autoRenew: true
    privacy: true
    consent: {
      agreedAt: consentTimestamp
      agreedBy: contactEmail
      agreementKeys: ['DNRA']
    }
    contactAdmin: {
      email: contactEmail
      nameFirst: contactFirstName
      nameLast: contactLastName
      phone: contactPhone
    }
    contactBilling: {
      email: contactEmail
      nameFirst: contactFirstName
      nameLast: contactLastName
      phone: contactPhone
    }
    contactRegistrant: {
      email: contactEmail
      nameFirst: contactFirstName
      nameLast: contactLastName
      phone: contactPhone
    }
    contactTech: {
      email: contactEmail
      nameFirst: contactFirstName
      nameLast: contactLastName
      phone: contactPhone
    }
  }
}

output domainName string = appServiceDomain.name
