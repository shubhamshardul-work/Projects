"""
Text cleaning and section segmentation for contract documents.
"""

import re


def clean_text(text: str) -> str:
    """Collapse whitespace and strip noise."""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.rstrip() for line in text.splitlines())
    return text.strip()


# Regex patterns for section headings commonly found in contracts
SECTION_PATTERNS = [
    r"^(\d+(?:\.\d+)*)\.\s+(.+)",                                  # 1.  1.1  10.2.3
    r"^(ARTICLE\s+[IVXLCDM\d]+)[:\.\s]+(.+)",                     # ARTICLE I
    r"^(Section\s+\d+(?:\.\d+)*)[:\.\s\u2014\-]+(.+)",             # Section 1:
    r"^((?:SCHEDULE|EXHIBIT|APPENDIX)\s+[A-Z0-9]+)[:\.\s\u2014\-]*(.*)",  # SCHEDULE A
]


def detect_sections(text: str) -> list[dict]:
    """
    Split text into sections based on heading patterns.
    Returns: [{heading, number, text}, ...]
    """
    lines = text.splitlines()
    sections: list[dict] = []
    current: dict = {"heading": "Preamble", "number": "0", "_lines": []}

    for line in lines:
        matched = False
        for pattern in SECTION_PATTERNS:
            m = re.match(pattern, line.strip(), re.IGNORECASE)
            if m:
                # Flush previous section
                if current["_lines"] or current["heading"] != "Preamble":
                    current["text"] = "\n".join(current.pop("_lines"))
                    sections.append(current)
                current = {
                    "heading": line.strip(),
                    "number": m.group(1),
                    "_lines": [],
                }
                matched = True
                break
        if not matched:
            current["_lines"].append(line)

    # Flush last section
    current["text"] = "\n".join(current.pop("_lines"))
    sections.append(current)
    return sections


def preprocess_document(raw: dict) -> dict:
    """
    Full preprocessing pipeline.
    Input: output of document_loader.load_document()
    Output: same dict + cleaned_text, sections
    """
    cleaned = clean_text(raw["full_text"])
    sections = detect_sections(cleaned)
    raw["cleaned_text"] = cleaned
    raw["sections"] = sections
    return raw
