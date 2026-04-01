"""
Semantic chunking for documents.
Uses embedding-based chunking for better extraction quality.
"""

import hashlib
from langchain_experimental.text_splitter import SemanticChunker
from config.llm_factory import get_embeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from typing import List

from config.settings import CHUNK_SIZE, CHUNK_OVERLAP, EMBEDDING_MODEL


def chunk_document(doc: Document, use_semantic: bool = True) -> List[Document]:
    """
    Split a document into chunks.
    - Semantic chunking preferred (uses embeddings to find natural break points)
    - Falls back to recursive character splitting for very large docs
    """
    if use_semantic:
        embeddings = get_embeddings()
        splitter = SemanticChunker(embeddings, breakpoint_threshold_type="percentile")
    else:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

    chunks = splitter.split_documents([doc])

    # Assign stable chunk IDs based on content hash
    for i, chunk in enumerate(chunks):
        content_hash = hashlib.md5(chunk.page_content.encode()).hexdigest()[:12]
        chunk.metadata["chunk_id"] = f"{doc.metadata.get('file_name', 'doc')}_{i}_{content_hash}"
        chunk.metadata["chunk_index"] = i
        chunk.metadata["total_chunks"] = len(chunks)

    return chunks
