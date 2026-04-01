"""
Document type classification using LLM.
Classifies documents into predefined types for metadata-driven processing.
"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.documents import Document

DOC_TYPES = [
    "SOW", "MSA", "ChangeOrder", "Invoice", "ProjectPlan",
    "MeetingNotes", "RiskRegister", "ResourcePlan", "StatusReport", "Unknown"
]


def classify_document(doc: Document, llm: BaseChatModel) -> str:
    """Use LLM to classify document type from first 1500 characters."""
    snippet = doc.page_content[:1500]
    prompt = f"""You are classifying a corporate consulting document.
Based on the following excerpt, classify the document as one of:
{', '.join(DOC_TYPES)}

Respond with ONLY the document type label, nothing else.

Excerpt:
{snippet}
"""
    response = llm.invoke(prompt)
    doc_type = response.content.strip()
    if doc_type not in DOC_TYPES:
        doc_type = "Unknown"
    doc.metadata["doc_type"] = doc_type
    return doc_type
