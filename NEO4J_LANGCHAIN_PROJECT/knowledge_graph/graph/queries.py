"""
Reusable Cypher query library for business insights.
Each function returns Cypher results for common analytical questions.
"""

from langchain_neo4j import Neo4jGraph


def get_client_history(graph: Neo4jGraph, client_name: str):
    """Q1: Full contractual history of a client."""
    return graph.query("""
        MATCH (c:Client {name: $name})<-[:CLIENT_OF]-(p:Project)
        OPTIONAL MATCH (p)<-[:GOVERNS]-(s:SOW)
        OPTIONAL MATCH (s)-[:AMENDED_BY]->(co:ChangeOrder)
        OPTIONAL MATCH (i:Invoice)-[:BILLED_TO]->(c)
        RETURN c, p, s, co, i
        ORDER BY s.effective_date
    """, params={"name": client_name})


def get_key_person_risk(graph: Neo4jGraph, person_name: str):
    """Q2: Key-person dependency risk."""
    return graph.query("""
        MATCH (person:Person {name: $name})-[:RESPONSIBLE_FOR]->(d:Deliverable)<-[:HAS_DELIVERABLE]-(p:Project)
        WHERE p.status = "Active"
        WITH p, count(d) AS deliverables_owned
        MATCH (p)<-[:RESPONSIBLE_FOR]-(other_person:Person)
        WHERE other_person.name <> $name
        WITH p, deliverables_owned, count(other_person) AS other_leads
        WHERE other_leads = 0
        RETURN p.name AS at_risk_project, deliverables_owned
    """, params={"name": person_name})


def get_uninvoiced_change_orders(graph: Neo4jGraph):
    """Q3: Revenue leakage — change orders not yet invoiced."""
    return graph.query("""
        MATCH (co:ChangeOrder)<-[:AMENDED_BY]-(s:SOW)<-[:BILLED_UNDER]-(i:Invoice)
        WITH co, collect(i) AS invoices
        WHERE size(invoices) = 0
        RETURN co.doc_id, co.change_description, co.value_delta, co.approved_date
        ORDER BY co.approved_date
    """)


def get_high_risk_clause_projects(graph: Neo4jGraph, clause_number: str):
    """Q4: Projects referencing a high-risk clause."""
    return graph.query("""
        MATCH (cl:Clause {clause_number: $clause})<-[:REFERENCES_CLAUSE]-(r:Risk)<-[:HAS_RISK]-(p:Project)
        WHERE p.status = "Active"
        RETURN p.name, r.description, r.severity, r.status
    """, params={"clause": clause_number})


def get_most_amended_clients(graph: Neo4jGraph, limit: int = 10):
    """Q5: Cross-project pattern — clients with most amendments."""
    return graph.query("""
        MATCH (c:Client)<-[:CLIENT_OF]-(p:Project)<-[:GOVERNS]-(s:SOW)-[:AMENDED_BY]->(co:ChangeOrder)
        RETURN c.name AS client, count(co) AS total_amendments
        ORDER BY total_amendments DESC
        LIMIT $limit
    """, params={"limit": limit})


def get_deliverable_provenance(graph: Neo4jGraph, deliverable_name: str):
    """Q6: Deliverable provenance — which SOW clause defines this deliverable."""
    return graph.query("""
        MATCH (d:Deliverable {name: $name})
        MATCH (d)<-[:HAS_DELIVERABLE]-(p:Project)<-[:GOVERNS]-(s:SOW)-[:CONTAINS_CLAUSE]->(cl:Clause)
        RETURN d.name, p.name, s.title, cl.clause_number, cl.title
    """, params={"name": deliverable_name})


def get_multi_client_people(graph: Neo4jGraph):
    """Q7: Find all people who have worked across multiple clients."""
    return graph.query("""
        MATCH (p:Person)-[:ASSIGNED_TO]->(proj:Project)-[:CLIENT_OF]->(c:Client)
        WITH p, collect(DISTINCT c.name) AS clients
        WHERE size(clients) > 1
        RETURN p.name, p.role, clients
        ORDER BY size(clients) DESC
    """)
