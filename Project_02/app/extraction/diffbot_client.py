"""
Diffbot Natural Language API wrapper with response caching.

API reference: https://docs.diffbot.com/reference/nl-post
- POST https://nl.diffbot.com/v1/?token=TOKEN&fields=[...]
- Body: {"content": "...", "lang": "en", "format": "plain text"}
- Response: {entities: [...], facts: [...], sentiment: float}

Diffbot "facts" represent both:
  - Entity-to-entity relationships  e.g. [PersonA] employee of [OrgB]
  - Entity-to-literal properties    e.g. [OrgA] number of employees [137000]
Each fact has: entity, property, value, confidence, evidence.
"""

import json
import logging
from pathlib import Path

import requests

from app.config import (
    DIFFBOT_API_TOKEN,
    DIFFBOT_MAX_CHUNK_CHARS,
    DIFFBOT_NL_FIELDS,
    EXTRACTED_DIR,
)

logger = logging.getLogger(__name__)

DIFFBOT_NL_URL = "https://nl.diffbot.com/v1/"


def _normalise_entity(entity: dict) -> dict:
    """
    Flatten Diffbot entity into a simpler dict consumed by the mappers.

    Diffbot entities carry type info in ``allTypes`` (a list of dicts).
    We extract the primary type as a top-level ``type`` string so downstream
    code can use ``entity["type"]`` directly.
    """
    all_types = entity.get("allTypes", [])
    primary_type = all_types[0]["name"] if all_types else "Misc"
    # Capitalise to match our ontology expectations (Person, Organization, …)
    primary_type = primary_type.strip().title()
    entity["type"] = primary_type
    entity["allTypeNames"] = [t.get("name", "") for t in all_types]
    return entity


def _split_facts(
    facts: list[dict], entities: list[dict]
) -> tuple[list[dict], list[dict]]:
    """
    Split Diffbot facts into **relationships** (entity→entity) and
    **properties** (entity→literal / non-entity value).

    A fact's ``value`` refers to another entity when it carries an
    ``entityIndex`` that points to a recognised entity *with a name*.
    Otherwise it is treated as a property/literal on the source entity.
    """
    relationships: list[dict] = []
    properties: list[dict] = []

    entity_names = {e.get("name", "").lower() for e in entities if e.get("name")}

    for fact in facts:
        entity_ref = fact.get("entity", {})
        value_ref = fact.get("value", {})
        prop_ref = fact.get("property", {})

        value_name = value_ref.get("name", "")
        # If the value is also a recognised entity, treat as relationship
        if value_name.lower() in entity_names and value_ref.get("allTypes"):
            relationships.append(
                {
                    "entity": entity_ref,
                    "value": value_ref,
                    "property": prop_ref,
                    "confidence": fact.get("confidence", 0.5),
                    "humanReadable": fact.get("humanReadable", ""),
                    "evidence": fact.get("evidence", []),
                }
            )
        else:
            properties.append(
                {
                    "entity_name": entity_ref.get("name", ""),
                    "property_name": prop_ref.get("name", ""),
                    "property_uri": prop_ref.get("diffbotUri", ""),
                    "value": value_name,
                    "confidence": fact.get("confidence", 0.5),
                }
            )

    return relationships, properties


def _call_diffbot(text: str) -> dict:
    """Single call to the Diffbot NL API."""
    fields = json.loads(DIFFBOT_NL_FIELDS)
    resp = requests.post(
        DIFFBOT_NL_URL,
        params={"token": DIFFBOT_API_TOKEN, "fields": ",".join(fields)},
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        json={"content": text, "lang": "en", "format": "plain text"},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def extract_entities_and_facts(
    text: str,
    document_id: str,
    cache_dir: str | None = None,
) -> dict:
    """
    Send text to Diffbot NL API.  Caches the raw + normalised response.
    Handles chunking for texts exceeding DIFFBOT_MAX_CHUNK_CHARS.

    Returns::

        {
            "document_id": ...,
            "entities": [...]          # normalised — each has ``type`` string
            "relationships": [...]     # entity-to-entity facts
            "properties": [...]        # entity-to-literal facts
            "sentiment": float | None
        }
    """
    cache_dir = cache_dir or EXTRACTED_DIR
    cache_path = Path(cache_dir) / f"{document_id}.json"

    if cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))

    chunks = [
        text[i : i + DIFFBOT_MAX_CHUNK_CHARS]
        for i in range(0, len(text), DIFFBOT_MAX_CHUNK_CHARS)
    ]

    all_entities: list[dict] = []
    all_relationships: list[dict] = []
    all_properties: list[dict] = []
    sentiment_sum = 0.0

    for idx, chunk in enumerate(chunks):
        logger.info(
            "[%s] Calling Diffbot chunk %d/%d (%d chars)",
            document_id, idx + 1, len(chunks), len(chunk),
        )
        result = _call_diffbot(chunk)

        raw_entities = result.get("entities", [])
        raw_facts = result.get("facts", [])
        sentiment_sum += result.get("sentiment", 0.0)

        entities = [_normalise_entity(e) for e in raw_entities]
        rels, props = _split_facts(raw_facts, entities)

        all_entities.extend(entities)
        all_relationships.extend(rels)
        all_properties.extend(props)

    merged = {
        "document_id": document_id,
        "entities": all_entities,
        "relationships": all_relationships,
        "properties": all_properties,
        "sentiment": sentiment_sum / len(chunks) if chunks else 0.0,
    }

    Path(cache_dir).mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(merged, indent=2, default=str), encoding="utf-8")
    return merged


def extract_by_section(sections: list[dict], document_id: str) -> list[dict]:
    """
    Extract entities / facts per section, tagged with section metadata.
    Sections shorter than 50 chars are skipped.
    """
    results: list[dict] = []
    for i, section in enumerate(sections):
        text = section.get("text", "")
        if len(text.strip()) < 50:
            continue
        section_id = f"{document_id}_SEC-{i:03d}"
        result = extract_entities_and_facts(text, section_id)
        result["section_heading"] = section.get("heading", "")
        result["section_number"] = section.get("number", "")
        results.append(result)
    return results
