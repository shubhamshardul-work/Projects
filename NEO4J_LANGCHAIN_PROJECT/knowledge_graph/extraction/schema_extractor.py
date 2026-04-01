"""
Stage B: Structured Output Schema Extraction.

Replaces the deprecated LLMGraphTransformer from langchain-experimental.
Uses Pydantic models + ChatOpenAI.with_structured_output() for schema-constrained
extraction that maps Diffbot's generic entities to the domain ontology.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any
from langchain_core.documents import Document

from config.ontology import ALLOWED_NODES, ALLOWED_RELATIONSHIPS, NODE_PROPERTIES
from config.llm_factory import get_llm_with_structured_output


# --- Pydantic models for structured output ---

class ExtractedNode(BaseModel):
    """A single entity extracted from the text, mapped to the domain ontology."""
    id: str = Field(
        ...,
        description="Unique identifier for the entity (use the entity's name or canonical ID)"
    )
    type: str = Field(
        ...,
        description=f"One of: {', '.join(ALLOWED_NODES)}"
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Properties of the entity as key-value pairs"
    )


class ExtractedEdge(BaseModel):
    """A relationship between two entities, mapped to the domain ontology."""
    source_id: str = Field(..., description="ID of the source entity")
    target_id: str = Field(..., description="ID of the target entity")
    type: str = Field(
        ...,
        description=f"One of: {', '.join(ALLOWED_RELATIONSHIPS)}"
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Properties of the relationship as key-value pairs"
    )


class GraphExtraction(BaseModel):
    """Complete graph extraction from a text chunk."""
    nodes: List[ExtractedNode] = Field(
        default_factory=list,
        description="Extracted entities"
    )
    edges: List[ExtractedEdge] = Field(
        default_factory=list,
        description="Extracted relationships"
    )


# --- System prompt for extraction ---

EXTRACTION_SYSTEM_PROMPT = """You are an expert knowledge graph extraction engine for an enterprise consulting firm.

Given text about consulting projects, contracts, and business operations, extract entities and relationships
using ONLY the following predefined types.

ALLOWED NODE TYPES: {allowed_nodes}
ALLOWED RELATIONSHIP TYPES: {allowed_relationships}

NODE PROPERTY SCHEMAS:
{property_schemas}

RULES:
1. Extract ONLY node types from the allowed list — never use generic types like 'Organization' or 'Company'
2. Extract ONLY relationship types from the allowed list
3. Use the entity's name as the 'id' field
4. Include all relevant properties you can extract from the text (refer to the property schemas above)
5. If you cannot confidently extract something, omit it — do not hallucinate
6. Map generic entities to domain types: 'Organization' → 'Client' or 'BusinessUnit', 'Agreement' → 'SOW'
7. Dates should be in ISO format (YYYY-MM-DD) when possible
8. Monetary values should include currency information in properties
""".format(
    allowed_nodes=", ".join(ALLOWED_NODES),
    allowed_relationships=", ".join(ALLOWED_RELATIONSHIPS),
    property_schemas="\n".join(
        f"  {node_type}: {', '.join(props)}"
        for node_type, props in NODE_PROPERTIES.items()
    ),
)


def create_schema_extractor() -> callable:
    """
    Create a structured output extractor using Pydantic models.

    This replaces the deprecated LLMGraphTransformer. Instead of relying on
    langchain-experimental, we use structured output from an LLM provider:
    - Guarantees output conforms to the Pydantic schema
    - Uses native function calling / structured output mode
    - Gives strict type enforcement — no schema leakage
    - Is actively maintained and supported
    """
    return get_llm_with_structured_output(schema=GraphExtraction, temperature=0.0)


def extract_with_structured_output(
    enriched_docs: List[Document],
    extractor: callable,
    batch_size: int = 10
) -> List[GraphExtraction]:
    """
    Run structured output extraction on Diffbot-enriched documents.
    Returns GraphExtraction objects conforming to your domain ontology.
    """
    all_extractions = []

    for i in range(0, len(enriched_docs), batch_size):
        batch = enriched_docs[i:i + batch_size]
        for doc in batch:
            try:
                extraction = extractor.invoke([
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": doc.page_content}
                ])
                # Validate: filter out any nodes/edges with disallowed types
                extraction.nodes = [
                    n for n in extraction.nodes if n.type in ALLOWED_NODES
                ]
                extraction.edges = [
                    e for e in extraction.edges if e.type in ALLOWED_RELATIONSHIPS
                ]
                all_extractions.append(extraction)
            except Exception as e:
                print(f"Structured output extraction failed for chunk: {e}")

    return all_extractions
