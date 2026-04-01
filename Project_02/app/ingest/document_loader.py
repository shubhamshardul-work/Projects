"""
Extract raw text from PDF and DOCX files.
"""

from pathlib import Path

import pdfplumber
from docx import Document as DocxDocument


def extract_text_from_pdf(file_path: str) -> dict:
    """Extract text page-by-page from a digital PDF."""
    pages = []
    with pdfplumber.open(file_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            pages.append({"page_number": i + 1, "text": text})
    full_text = "\n\n".join(p["text"] for p in pages)
    return {"pages": pages, "full_text": full_text}


def extract_text_from_docx(file_path: str) -> dict:
    """Extract text paragraph-by-paragraph from a DOCX file."""
    doc = DocxDocument(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(paragraphs)
    return {"paragraphs": paragraphs, "full_text": full_text}


def load_document(file_path: str) -> dict:
    """
    Route to the correct extractor based on file extension.
    Returns: {file_path, file_type, full_text, details}
    """
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        result = extract_text_from_pdf(file_path)
        return {
            "file_path": file_path,
            "file_type": "pdf",
            "full_text": result["full_text"],
            "details": result,
        }
    elif ext == ".docx":
        result = extract_text_from_docx(file_path)
        return {
            "file_path": file_path,
            "file_type": "docx",
            "full_text": result["full_text"],
            "details": result,
        }
    elif ext == ".txt":
        text = Path(file_path).read_text(encoding="utf-8")
        return {
            "file_path": file_path,
            "file_type": "txt",
            "full_text": text,
            "details": {},
        }
    else:
        raise ValueError(f"Unsupported file type: {ext}")
