"""
Canonical ontology for the Contract Intelligence Knowledge Graph.
This is the single source of truth for node types, relationship types,
and property schemas. The mapper and loader enforce this.
"""

from enum import Enum


class NodeType(str, Enum):
    CLIENT = "Client"
    ACCOUNT = "Account"
    ENGAGEMENT = "Engagement"
    PROJECT = "Project"
    CONTRACT = "Contract"
    MSA = "MSA"
    SOW = "SOW"
    AMENDMENT = "Amendment"
    CHANGE_REQUEST = "ChangeRequest"
    CLAUSE = "Clause"
    SECTION = "Section"
    DELIVERABLE = "Deliverable"
    MILESTONE = "Milestone"
    SLA = "SLA"
    KPI = "KPI"
    PRICING_MODEL = "PricingModel"
    RESOURCE_ROLE = "ResourceRole"
    LEGAL_ENTITY = "LegalEntity"
    LOCATION = "Location"
    VERSION = "Version"


class RelationshipType(str, Enum):
    HAS_ACCOUNT = "HAS_ACCOUNT"
    HAS_ENGAGEMENT = "HAS_ENGAGEMENT"
    HAS_PROJECT = "HAS_PROJECT"
    GOVERNED_BY = "GOVERNED_BY"
    HAS_SOW = "HAS_SOW"
    HAS_AMENDMENT = "HAS_AMENDMENT"
    HAS_CLAUSE = "HAS_CLAUSE"
    HAS_DELIVERABLE = "HAS_DELIVERABLE"
    HAS_MILESTONE = "HAS_MILESTONE"
    TRACKED_BY = "TRACKED_BY"
    MODIFIED_BY = "MODIFIED_BY"
    SUPERSEDED_BY = "SUPERSEDED_BY"
    REFERS_TO = "REFERS_TO"
    USES_PRICING_MODEL = "USES_PRICING_MODEL"
    DELIVERED_BY = "DELIVERED_BY"
    HAS_SECTION = "HAS_SECTION"
    REVISED_BY = "REVISED_BY"
    HAS_VERSION = "HAS_VERSION"
    HAS_SLA = "HAS_SLA"
    HAS_KPI = "HAS_KPI"
    BELONGS_TO = "BELONGS_TO"


# Property schemas per node type — used for validation and LLM mapper prompts
NODE_PROPERTY_SCHEMA: dict[NodeType, dict] = {
    NodeType.CLIENT: {
        "required": ["id", "name"],
        "optional": ["industry", "headquarters"],
    },
    NodeType.ACCOUNT: {
        "required": ["id", "name"],
        "optional": ["accountManager", "region"],
    },
    NodeType.ENGAGEMENT: {
        "required": ["id", "name"],
        "optional": ["type", "startDate", "endDate"],
    },
    NodeType.PROJECT: {
        "required": ["id", "name"],
        "optional": ["status", "startDate", "endDate"],
    },
    NodeType.CONTRACT: {
        "required": ["id", "title"],
        "optional": ["effectiveDate", "expiryDate", "status"],
    },
    NodeType.MSA: {
        "required": ["id", "title"],
        "optional": ["effectiveDate", "expiryDate", "parties"],
    },
    NodeType.SOW: {
        "required": ["id", "title"],
        "optional": ["startDate", "endDate", "value", "currency", "status"],
    },
    NodeType.AMENDMENT: {
        "required": ["id", "title"],
        "optional": ["effectiveDate", "description", "amendmentNumber"],
    },
    NodeType.CHANGE_REQUEST: {
        "required": ["id", "title"],
        "optional": ["requestDate", "status", "description", "impact"],
    },
    NodeType.CLAUSE: {
        "required": ["id", "clauseNumber"],
        "optional": ["title", "text", "category", "isCurrent"],
    },
    NodeType.SECTION: {
        "required": ["id", "title"],
        "optional": ["sectionNumber", "text", "pageNumber"],
    },
    NodeType.DELIVERABLE: {
        "required": ["id", "name"],
        "optional": ["description", "dueDate", "status"],
    },
    NodeType.MILESTONE: {
        "required": ["id", "name"],
        "optional": ["dueDate", "status", "paymentAmount"],
    },
    NodeType.SLA: {
        "required": ["id", "name"],
        "optional": ["metric", "target", "penalty"],
    },
    NodeType.KPI: {
        "required": ["id", "name"],
        "optional": ["metric", "target", "frequency"],
    },
    NodeType.PRICING_MODEL: {
        "required": ["id", "type"],
        "optional": ["description", "rateCard", "currency"],
    },
    NodeType.RESOURCE_ROLE: {
        "required": ["id", "roleName"],
        "optional": ["rate", "currency", "level"],
    },
    NodeType.LEGAL_ENTITY: {
        "required": ["id", "name"],
        "optional": ["jurisdiction", "registrationNumber"],
    },
    NodeType.LOCATION: {
        "required": ["id", "name"],
        "optional": ["country", "city", "address"],
    },
    NodeType.VERSION: {
        "required": ["id", "versionNumber"],
        "optional": ["createdDate", "changeDescription"],
    },
}


# Allowed relationship directions: (from_type, to_type) -> RelationshipType
VALID_RELATIONSHIPS: dict[tuple[NodeType, NodeType], RelationshipType] = {
    (NodeType.CLIENT, NodeType.ACCOUNT): RelationshipType.HAS_ACCOUNT,
    (NodeType.ACCOUNT, NodeType.ENGAGEMENT): RelationshipType.HAS_ENGAGEMENT,
    (NodeType.ENGAGEMENT, NodeType.PROJECT): RelationshipType.HAS_PROJECT,
    (NodeType.PROJECT, NodeType.CONTRACT): RelationshipType.GOVERNED_BY,
    (NodeType.CONTRACT, NodeType.SOW): RelationshipType.HAS_SOW,
    (NodeType.CONTRACT, NodeType.AMENDMENT): RelationshipType.HAS_AMENDMENT,
    (NodeType.SOW, NodeType.CLAUSE): RelationshipType.HAS_CLAUSE,
    (NodeType.SOW, NodeType.SECTION): RelationshipType.HAS_SECTION,
    (NodeType.SOW, NodeType.DELIVERABLE): RelationshipType.HAS_DELIVERABLE,
    (NodeType.SOW, NodeType.MILESTONE): RelationshipType.HAS_MILESTONE,
    (NodeType.SOW, NodeType.PRICING_MODEL): RelationshipType.USES_PRICING_MODEL,
    (NodeType.SOW, NodeType.SLA): RelationshipType.HAS_SLA,
    (NodeType.SOW, NodeType.KPI): RelationshipType.HAS_KPI,
    (NodeType.DELIVERABLE, NodeType.SLA): RelationshipType.TRACKED_BY,
    (NodeType.CLAUSE, NodeType.AMENDMENT): RelationshipType.MODIFIED_BY,
    (NodeType.CLAUSE, NodeType.CLAUSE): RelationshipType.REFERS_TO,
    (NodeType.PROJECT, NodeType.RESOURCE_ROLE): RelationshipType.DELIVERED_BY,
    (NodeType.SOW, NodeType.AMENDMENT): RelationshipType.REVISED_BY,
}
