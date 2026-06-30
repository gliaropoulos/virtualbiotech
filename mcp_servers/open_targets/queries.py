"""Centralized GraphQL query strings for the Open Targets v4 API.

Kept in one place so field paths can be validated against the live schema and adjusted without
touching tool logic. Endpoint: https://api.platform.opentargets.org/api/v4/graphql (POST).
Schema reference: https://platform-docs.opentargets.org/data-access/graphql-api
"""

SEARCH = """
query Search($q: String!, $entities: [String!]) {
  search(queryString: $q, entityNames: $entities) {
    hits {
      id
      name
      entity
      object {
        __typename
        ... on Target { approvedSymbol approvedName biotype }
        ... on Disease { name therapeuticAreas { id name } }
        ... on Drug { name drugType }
      }
    }
  }
}
"""

TARGET_DETAILS = """
query Target($ensemblId: String!) {
  target(ensemblId: $ensemblId) {
    id
    approvedSymbol
    approvedName
    biotype
    functionDescriptions
    proteinIds { id source }
    subcellularLocations { location source }
    tractability { label modality value }
    safetyLiabilities { event eventId datasource }
  }
}
"""

# Association breakdown is how the paper derived the binary "genetic evidence" indicator: the
# genetic_association datatype score on a target-disease pair.
TARGET_ASSOCIATED_DISEASES = """
query TargetAssoc($ensemblId: String!, $size: Int!) {
  target(ensemblId: $ensemblId) {
    id
    approvedSymbol
    associatedDiseases(page: { index: 0, size: $size }) {
      count
      rows {
        disease { id name }
        score
        datatypeScores { id score }
      }
    }
  }
}
"""

TARGET_KNOWN_DRUGS = """
query KnownDrugs($ensemblId: String!) {
  target(ensemblId: $ensemblId) {
    id
    approvedSymbol
    drugAndClinicalCandidates {
      count
      rows {
        id
        maxClinicalStage
        drug {
          id
          name
          drugType
          maximumClinicalStage
          mechanismsOfAction {
            rows { mechanismOfAction actionType }
          }
        }
        diseases { disease { id name } diseaseFromSource }
        clinicalReports { id clinicalStage trialOverallStatus title }
      }
    }
  }
}
"""

DISEASE_DETAILS = """
query Disease($efoId: String!) {
  disease(efoId: $efoId) {
    id
    name
    description
    therapeuticAreas { id name }
  }
}
"""
