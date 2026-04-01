"""
Streamlit UI for Contract Intelligence Knowledge Graph.

Tabs:
  1. Upload & Process — upload docs, pick mapper mode, run pipeline
  2. Review Queue    — review flagged items (human-in-the-loop)
  3. Query           — ask natural language questions (Graph RAG)
  4. Graph Explorer   — stats + custom Cypher
"""

from __future__ import annotations

import requests
import streamlit as st
import pandas as pd

API_BASE = "http://localhost:8000/api/v1"

st.set_page_config(page_title="Contract Intelligence KG", layout="wide")
st.title("Contract Intelligence Knowledge Graph")

# ── Session state defaults ──────────────────────────────────────────────────

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "pipeline_status" not in st.session_state:
    st.session_state.pipeline_status = None
if "review_items" not in st.session_state:
    st.session_state.review_items = []

# ── Tabs ────────────────────────────────────────────────────────────────────

tab_upload, tab_review, tab_query, tab_explorer = st.tabs(
    ["Upload & Process", "Review Queue", "Query", "Graph Explorer"]
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tab 1: Upload & Process
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab_upload:
    st.header("Upload & Process Document")

    uploaded_file = st.file_uploader(
        "Upload a contract document (PDF, DOCX, TXT)",
        type=["pdf", "docx", "txt"],
    )

    col1, col2 = st.columns(2)
    with col1:
        client_name = st.text_input("Client Name (optional)")
    with col2:
        project_name = st.text_input("Project Name (optional)")

    mapper_mode = st.radio(
        "Mapper Mode",
        options=["rule", "llm"],
        format_func=lambda x: "Rule-based (fast, deterministic)" if x == "rule" else "LLM-based (flexible, costs tokens)",
        horizontal=True,
    )

    if st.button("Process Document", disabled=uploaded_file is None, type="primary"):
        with st.spinner("Running pipeline…"):
            try:
                resp = requests.post(
                    f"{API_BASE}/documents/upload",
                    files={"file": (uploaded_file.name, uploaded_file.getvalue())},
                    params={
                        "client_name": client_name,
                        "project_name": project_name,
                        "mapper_mode": mapper_mode,
                    },
                    timeout=300,
                )
                resp.raise_for_status()
                data = resp.json()

                st.session_state.thread_id = data.get("thread_id")
                st.session_state.pipeline_status = data.get("status")

                if data["status"] == "review":
                    st.session_state.review_items = data.get("review_items", [])
                    st.warning(
                        f"Pipeline paused — {len(st.session_state.review_items)} item(s) need review. "
                        "Go to the **Review Queue** tab."
                    )
                elif data["status"] == "completed":
                    st.success("Pipeline completed successfully!")
                    summary = data.get("ingestion_summary", {})
                    st.json(summary)
                else:
                    st.error(f"Pipeline ended with status: {data['status']}")
                    st.json(data)

            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to the API server. Is it running on localhost:8000?")
            except Exception as e:
                st.error(f"Error: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tab 2: Review Queue
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab_review:
    st.header("Human Review Queue")

    # Poll for status if we have a thread_id
    if st.session_state.thread_id and st.button("Refresh Status"):
        try:
            resp = requests.get(
                f"{API_BASE}/pipeline/{st.session_state.thread_id}/status",
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            st.session_state.pipeline_status = data.get("status")
            st.session_state.review_items = data.get("review_items", [])
        except Exception as e:
            st.error(f"Error polling status: {e}")

    review_items = st.session_state.review_items
    if not review_items:
        st.info("No items pending review.")
    else:
        st.write(f"**{len(review_items)} item(s)** need your decision:")

        decisions: list[dict] = []

        for i, item in enumerate(review_items):
            with st.expander(f"#{i + 1} — {item.get('entity_name', 'Unknown')} ({item.get('reason', '')})"):
                st.write(f"**Diffbot type:** {item.get('diffbot_type', 'N/A')}")
                st.write(f"**Suggested type:** {item.get('suggested_node_type', 'N/A')}")
                st.write(f"**Confidence:** {item.get('confidence', 0.0):.2f}")
                st.write(f"**Section:** {item.get('section_heading', 'N/A')}")

                action = st.selectbox(
                    "Action",
                    options=["approve", "edit", "reject"],
                    key=f"action_{i}",
                )

                new_type = None
                if action == "edit":
                    from app.models.ontology import NodeType
                    new_type = st.selectbox(
                        "Correct node type",
                        options=[nt.value for nt in NodeType],
                        key=f"type_{i}",
                    )

                decisions.append(
                    {
                        "item_id": item.get("item_id", f"item-{i}"),
                        "action": action,
                        "new_node_type": new_type,
                        "new_properties": {"name": item.get("entity_name", "")} if action == "edit" else None,
                    }
                )

        if st.button("Submit Review & Resume Pipeline", type="primary"):
            with st.spinner("Submitting review…"):
                try:
                    resp = requests.post(
                        f"{API_BASE}/pipeline/{st.session_state.thread_id}/review",
                        json={"decisions": decisions},
                        timeout=300,
                    )
                    resp.raise_for_status()
                    data = resp.json()

                    st.session_state.pipeline_status = data.get("status")
                    st.session_state.review_items = []

                    if data["status"] == "completed":
                        st.success("Pipeline completed after review!")
                        st.json(data.get("ingestion_summary", {}))
                    else:
                        st.warning(f"Pipeline status: {data['status']}")
                except Exception as e:
                    st.error(f"Error submitting review: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tab 3: Query
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab_query:
    st.header("Query the Knowledge Graph")

    st.markdown(
        "Ask questions in plain English. The system generates a Cypher query, "
        "runs it against Neo4j, and returns a natural-language answer."
    )

    # Suggested questions
    with st.expander("Suggested questions"):
        suggestions = [
            "What deliverables are in SOW-123?",
            "Which clauses were changed by amendment AMD-001?",
            "Show the amendment lineage for SOW-200",
            "List all SOWs under Contract-10",
            "What pricing model is used in SOW-123?",
        ]
        for s in suggestions:
            if st.button(s, key=f"suggest_{s}"):
                st.session_state["query_input"] = s

    question = st.text_input(
        "Your question",
        value=st.session_state.get("query_input", ""),
        key="query_box",
    )

    if st.button("Ask", disabled=not question, type="primary"):
        with st.spinner("Querying…"):
            try:
                resp = requests.post(
                    f"{API_BASE}/query",
                    json={"question": question},
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()

                st.subheader("Answer")
                st.write(data.get("answer", "No answer returned."))

                st.subheader("Generated Cypher")
                st.code(data.get("cypher", ""), language="cypher")

            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to the API server.")
            except Exception as e:
                st.error(f"Error: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Tab 4: Graph Explorer
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

with tab_explorer:
    st.header("Graph Explorer")

    # Stats
    if st.button("Load Graph Stats"):
        try:
            resp = requests.get(f"{API_BASE}/graph/stats", timeout=30)
            resp.raise_for_status()
            stats = resp.json()

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Nodes", stats.get("total_nodes", 0))
            with col2:
                st.metric("Total Relationships", stats.get("total_relationships", 0))

            st.write("**Node Labels:**", ", ".join(stats.get("node_labels", [])))
            st.write("**Relationship Types:**", ", ".join(stats.get("relationship_types", [])))
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to the API server.")
        except Exception as e:
            st.error(f"Error: {e}")

    # Custom Cypher
    st.subheader("Run Custom Cypher")
    cypher = st.text_area("Cypher query", height=100, placeholder="MATCH (n) RETURN n LIMIT 25")
    if st.button("Execute", disabled=not cypher):
        try:
            from app.graph_db.neo4j_client import Neo4jClient

            client = Neo4jClient()
            results = client.query(cypher)
            if results:
                st.dataframe(pd.DataFrame(results))
            else:
                st.info("Query returned no results.")
        except Exception as e:
            st.error(f"Cypher error: {e}")
