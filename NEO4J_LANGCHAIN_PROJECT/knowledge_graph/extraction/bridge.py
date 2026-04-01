"""
Bridge between Stage A (Diffbot) and Stage B (Structured Output).
Converts Diffbot's GraphDocument objects into enriched LangChain Documents
so the structured output extractor has both raw text AND pre-extracted facts.
"""

from langchain_community.graphs.graph_document import GraphDocument
from langchain_core.documents import Document
from typing import List


def graphdocs_to_enriched_documents(
    graph_docs: List[GraphDocument]
) -> List[Document]:
    """
    Convert Diffbot GraphDocuments into enriched LangChain Documents.

    Strategy:
    - Preserve the original chunk text (page_content)
    - Inject Diffbot's extracted entities and relationships as structured context
    - This gives the structured output extractor BOTH the raw text AND pre-extracted facts
    - The LLM can then perform high-quality schema mapping without re-scanning raw text

    This is the bridge between Diffbot's generic schema and your domain ontology.
    """
    enriched_docs = []

    for gd in graph_docs:
        # 1. Collect extracted entity descriptions
        entity_lines = []
        for node in gd.nodes:
            props = ", ".join([f"{k}={v}" for k, v in node.properties.items()])
            entity_lines.append(
                f"ENTITY: {node.id} | Type: {node.type}"
                + (f" | Properties: {props}" if props else "")
            )

        # 2. Collect extracted relationship descriptions
        rel_lines = []
        for rel in gd.relationships:
            rel_lines.append(
                f"RELATION: {rel.source.id} --[{rel.type}]--> {rel.target.id}"
            )

        # 3. Build enriched content block
        enriched_content = gd.source.page_content

        if entity_lines or rel_lines:
            enriched_content += "\n\n--- EXTRACTED CONTEXT (from NLP pre-processing) ---\n"
            if entity_lines:
                enriched_content += "\nIdentified entities:\n" + "\n".join(entity_lines)
            if rel_lines:
                enriched_content += "\n\nIdentified relationships:\n" + "\n".join(rel_lines)

        enriched_doc = Document(
            page_content=enriched_content,
            metadata={
                **gd.source.metadata,
                "diffbot_node_count": len(gd.nodes),
                "diffbot_rel_count": len(gd.relationships),
                "bridge_processed": True
            }
        )
        enriched_docs.append(enriched_doc)

    return enriched_docs
