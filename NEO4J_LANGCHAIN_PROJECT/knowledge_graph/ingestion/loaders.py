"""
Document loaders for various file types.
Maps file extensions to LangChain document loader classes.
"""

from pathlib import Path
from langchain_community.document_loaders import (
    PyPDFLoader,
    Docx2txtLoader,
    UnstructuredExcelLoader,
    UnstructuredEmailLoader,
    TextLoader,
)
from langchain_core.documents import Document
from typing import List

LOADER_MAP = {
    ".pdf":  PyPDFLoader,
    ".docx": Docx2txtLoader,
    ".doc":  Docx2txtLoader,
    ".xlsx": UnstructuredExcelLoader,
    ".xls":  UnstructuredExcelLoader,
    ".msg":  UnstructuredEmailLoader,
    ".eml":  UnstructuredEmailLoader,
    ".txt":  TextLoader,
}


def load_document(file_path: str) -> List[Document]:
    """Load a single document file into LangChain Document objects."""
    ext = Path(file_path).suffix.lower()
    loader_cls = LOADER_MAP.get(ext)
    if not loader_cls:
        raise ValueError(f"Unsupported file type: {ext}")
    loader = loader_cls(file_path)
    docs = loader.load()
    # Inject base metadata
    for doc in docs:
        doc.metadata["file_path"] = file_path
        doc.metadata["file_name"] = Path(file_path).name
        doc.metadata["file_type"] = ext
    return docs


def load_directory(directory_path: str) -> List[Document]:
    """Recursively load all supported documents from a directory."""
    all_docs = []
    for path in Path(directory_path).rglob("*"):
        if path.suffix.lower() in LOADER_MAP:
            try:
                all_docs.extend(load_document(str(path)))
            except Exception as e:
                print(f"Failed to load {path}: {e}")
    return all_docs
