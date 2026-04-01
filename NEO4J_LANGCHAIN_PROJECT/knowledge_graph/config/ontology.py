"""
Domain ontology configuration for the Enterprise Knowledge Graph.

Defines the allowed node types, relationship types, and node properties
that govern what can be extracted and written to Neo4j.

This is the single source of truth for schema enforcement.
"""

ALLOWED_NODES = [
    "Client",
    "Project",
    "Person",
    "SOW",
    "Deliverable",
    "Milestone",
    "ChangeOrder",
    "Invoice",
    "Risk",
    "Clause",
    "BusinessUnit",
]

ALLOWED_RELATIONSHIPS = [
    "SIGNED_BY",
    "GOVERNS",
    "AMENDED_BY",
    "HAS_DELIVERABLE",
    "HAS_MILESTONE",
    "HAS_RISK",
    "RESPONSIBLE_FOR",
    "ASSIGNED_TO",
    "BILLED_UNDER",
    "BILLED_TO",
    "REFERENCES_CLAUSE",
    "CONTAINS_CLAUSE",
    "DELIVERED_BY",
    "CLIENT_OF",
]

NODE_PROPERTIES = {
    "Client":       ["name", "industry", "region", "canonical_id"],
    "Project":      ["project_id", "name", "status", "start_date", "end_date", "total_value"],
    "Person":       ["name", "role", "email", "employer", "canonical_id"],
    "SOW":          ["doc_id", "title", "effective_date", "expiry_date", "contract_value", "currency"],
    "Deliverable":  ["name", "due_date", "status", "acceptance_criteria"],
    "Milestone":    ["name", "due_date", "status"],
    "ChangeOrder":  ["doc_id", "amendment_number", "change_description", "value_delta", "approved_date"],
    "Invoice":      ["invoice_id", "amount", "currency", "invoice_date", "payment_status"],
    "Risk":         ["description", "severity", "category", "status", "mitigation"],
    "Clause":       ["clause_number", "title", "category"],
    "BusinessUnit": ["name", "practice_area", "geography"],
}
