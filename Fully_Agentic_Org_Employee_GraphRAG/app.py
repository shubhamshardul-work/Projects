"""
Streamlit Chat Application for Fully Agentic GraphRAG.

Features:
  - File upload (Excel/CSV) for new data
  - Automatic schema discovery & ingestion
  - Dynamic chat over any graph schema

Run:  streamlit run app.py
"""
import os
import tempfile
from pathlib import Path

import streamlit as st

from src.neo4j_manager import Neo4jManager
from src.graph_rag.agent import GraphRAGAgent
from src.data_loader import load_file
from src.schema_discovery.profiler import profile_data
from src.schema_discovery.schema_agent import infer_graph_schema
from src.ingestion.dynamic_ingest import run_dynamic_ingestion
from src.config import MAPPING_DIR


# ───────────────────────────────────────────────────────────────────────
# Page Config
# ───────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="OrgGraph AI — Agentic Intelligence",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ───────────────────────────────────────────────────────────────────────
# Custom CSS
# ───────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .stApp { font-family: 'Inter', sans-serif; }

    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.8rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.25);
    }
    .main-header h1 { color: white; font-size: 2rem; font-weight: 700; margin: 0; letter-spacing: -0.5px; }
    .main-header p { color: rgba(255,255,255,0.85); font-size: 0.95rem; margin: 0.3rem 0 0 0; font-weight: 300; }

    .stChatMessage { border-radius: 12px !important; margin-bottom: 0.5rem !important; }

    [data-testid="stSidebar"] { background: linear-gradient(180deg, #f8f9ff 0%, #eef1ff 100%); }

    .sidebar-card {
        background: white;
        padding: 1rem 1.2rem;
        border-radius: 12px;
        margin-bottom: 0.8rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        border: 1px solid rgba(102, 126, 234, 0.1);
    }
    .sidebar-card h4 { margin: 0 0 0.5rem 0; color: #4c4f69; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
    .sidebar-card p { margin: 0.2rem 0; color: #5c5f77; font-size: 0.82rem; }

    .stat-number {
        font-size: 1.8rem; font-weight: 700;
        background: linear-gradient(135deg, #667eea, #764ba2);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        line-height: 1.2;
    }

    .status-dot {
        display: inline-block; width: 8px; height: 8px; border-radius: 50%;
        margin-right: 6px; animation: pulse 2s infinite;
    }
    .status-connected { background: #40a02b; }
    .status-disconnected { background: #d20f39; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

    .upload-section {
        background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%);
        padding: 1.2rem;
        border-radius: 12px;
        margin: 0.8rem 0;
        border: 1px solid rgba(76, 175, 80, 0.2);
    }
</style>
""", unsafe_allow_html=True)


# ───────────────────────────────────────────────────────────────────────
# Session State Init
# ───────────────────────────────────────────────────────────────────────

if "messages" not in st.session_state:
    st.session_state.messages = []

if "agent" not in st.session_state:
    st.session_state.agent = None
    st.session_state.db = None
    st.session_state.connected = False
    st.session_state.graph_stats = None
    st.session_state.ingestion_done = False


# ───────────────────────────────────────────────────────────────────────
# Neo4j Connection
# ───────────────────────────────────────────────────────────────────────

def connect_neo4j():
    """Connect to Neo4j and optionally init agent if graph has data."""
    try:
        db = Neo4jManager()
        db.connect()
        stats = db.get_counts()
        st.session_state.db = db
        st.session_state.graph_stats = stats
        st.session_state.connected = True

        # If graph already has data, init the agent
        if stats["nodes"] > 0:
            agent = GraphRAGAgent(neo4j_manager=db)
            st.session_state.agent = agent
            st.session_state.ingestion_done = True

        return True
    except Exception as e:
        st.session_state.connected = False
        return False


if not st.session_state.connected:
    connect_neo4j()


# ───────────────────────────────────────────────────────────────────────
# Sidebar
# ───────────────────────────────────────────────────────────────────────

with st.sidebar:
    # Connection status
    if st.session_state.connected:
        st.markdown(
            '<p><span class="status-dot status-connected"></span>'
            '<strong>Neo4j Connected</strong></p>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<p><span class="status-dot status-disconnected"></span>'
            '<strong>Neo4j Disconnected</strong></p>',
            unsafe_allow_html=True,
        )
        st.error("Could not connect to Neo4j. Check `.env` settings.")

    # Graph stats
    if st.session_state.graph_stats:
        stats = st.session_state.graph_stats
        st.markdown(f"""
        <div class="sidebar-card">
            <h4>📊 Graph Statistics</h4>
            <p><span class="stat-number">{stats['nodes']}</span> nodes</p>
            <p><span class="stat-number">{stats['relationships']}</span> relationships</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # ── File Upload & Ingestion ──
    st.markdown("#### 📁 Upload & Ingest Data")
    st.caption("Upload any Excel or CSV file to build a knowledge graph automatically.")

    uploaded_file = st.file_uploader(
        "Choose a file",
        type=["xlsx", "xls", "csv"],
        key="file_uploader",
    )

    if uploaded_file and st.button("🚀 Analyze & Ingest", use_container_width=True, type="primary"):
        if not st.session_state.connected:
            st.error("Connect to Neo4j first!")
        else:
            # Save uploaded file to temp
            suffix = Path(uploaded_file.name).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name

            try:
                with st.spinner("📊 Loading & profiling data …"):
                    tables = load_file(tmp_path)
                    profile = profile_data(tables)
                    st.success(f"Loaded {len(tables)} tables")

                with st.spinner("🧠 LLM inferring graph schema …"):
                    save_path = str(Path(MAPPING_DIR) / f"{Path(uploaded_file.name).stem}_mapping.json")
                    mapping = infer_graph_schema(profile=profile, save_path=save_path)
                    st.success(f"Schema: {len(mapping.nodes)} nodes, {len(mapping.relationships)} relationships")

                with st.spinner("⚡ Ingesting into Neo4j …"):
                    counts = run_dynamic_ingestion(
                        db=st.session_state.db,
                        tables=tables,
                        mapping=mapping,
                        clear_first=True,
                    )
                    st.session_state.graph_stats = counts

                with st.spinner("🔄 Initializing chat agent …"):
                    agent = GraphRAGAgent(neo4j_manager=st.session_state.db)
                    st.session_state.agent = agent
                    st.session_state.ingestion_done = True
                    st.session_state.messages = []  # Clear old chat

                st.success(f"✅ Done! {counts['nodes']} nodes, {counts['relationships']} relationships")
                st.rerun()

            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
            finally:
                try:
                    os.unlink(tmp_path)
                except PermissionError:
                    pass  # Windows may still hold a lock on the temp file

    st.markdown("---")

    # Clear chat
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    # Refresh schema
    if st.session_state.agent and st.button("🔄 Refresh Schema", use_container_width=True):
        with st.spinner("Refreshing …"):
            st.session_state.agent.refresh_schema()
            st.session_state.graph_stats = st.session_state.db.get_counts()
        st.success("Schema refreshed!")
        st.rerun()

    # About
    st.markdown(f"""
    <div class="sidebar-card">
        <h4>ℹ️ About</h4>
        <p>Fully Agentic GraphRAG — upload <em>any</em>
        Excel/CSV to automatically build a Neo4j knowledge graph.
        The LLM infers the schema, ingests the data, and
        powers natural language queries. Zero hardcoding.</p>
    </div>
    """, unsafe_allow_html=True)


# ───────────────────────────────────────────────────────────────────────
# Main Content
# ───────────────────────────────────────────────────────────────────────

# Header
st.markdown("""
<div class="main-header">
    <h1>🔍 OrgGraph AI — Fully Agentic</h1>
    <p>Upload any data file → Auto-discover schema → Build knowledge graph → Ask questions</p>
</div>
""", unsafe_allow_html=True)

# Chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧑‍💼" if msg["role"] == "user" else "🤖"):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("cypher"):
            with st.expander("🔎 View Cypher Query", expanded=False):
                st.code(msg["cypher"], language="cypher")

# Chat input
if prompt := st.chat_input("Ask anything about your data …"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💼"):
        st.markdown(prompt)

    if not st.session_state.connected:
        error_msg = "❌ Not connected to Neo4j."
        st.session_state.messages.append({"role": "assistant", "content": error_msg})
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(error_msg)
    elif not st.session_state.agent:
        error_msg = "📁 No data loaded yet. Upload an Excel/CSV file in the sidebar to get started!"
        st.session_state.messages.append({"role": "assistant", "content": error_msg})
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(error_msg)
    else:
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("🧠 Thinking …"):
                try:
                    result = st.session_state.agent.query(prompt)
                    answer = result["answer"]
                    cypher = result.get("cypher", "")
                except Exception as e:
                    answer = f"❌ An error occurred: {str(e)}"
                    cypher = ""

            st.markdown(answer)
            if cypher:
                with st.expander("🔎 View Cypher Query", expanded=False):
                    st.code(cypher, language="cypher")

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "cypher": cypher,
        })

# Empty state
if not st.session_state.messages:
    if not st.session_state.ingestion_done:
        st.markdown("---")
        st.markdown("### 👋 Welcome! Get started in 3 steps:")
        cols = st.columns(3)
        steps = [
            ("1️⃣", "Upload Data", "Drop an Excel or CSV file in the sidebar"),
            ("2️⃣", "Auto-Build Graph", "The LLM discovers the schema and builds your knowledge graph"),
            ("3️⃣", "Ask Questions", "Chat with your data in natural language"),
        ]
        for col, (icon, title, desc) in zip(cols, steps):
            with col:
                st.markdown(f"""
                <div class="sidebar-card" style="text-align: center; padding: 1.5rem;">
                    <div style="font-size: 2rem; margin-bottom: 0.5rem;">{icon}</div>
                    <h4 style="text-transform: none; font-size: 1rem;">{title}</h4>
                    <p>{desc}</p>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.markdown("---")
        st.info("✅ Graph is loaded and ready. Start asking questions!")
