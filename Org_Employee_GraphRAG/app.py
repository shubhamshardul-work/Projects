"""
Streamlit Chat Application for Org Employee GraphRAG.

Run:  streamlit run app.py
"""
import streamlit as st

from src.neo4j_manager import Neo4jManager
from src.graph_rag.agent import GraphRAGAgent


# ───────────────────────────────────────────────────────────────────────
# Page Config
# ───────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="OrgGraph AI — Employee Intelligence",
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

    /* Global */
    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* Header */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.8rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(102, 126, 234, 0.25);
    }
    .main-header h1 {
        color: white;
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .main-header p {
        color: rgba(255,255,255,0.85);
        font-size: 0.95rem;
        margin: 0.3rem 0 0 0;
        font-weight: 300;
    }

    /* Chat messages */
    .stChatMessage {
        border-radius: 12px !important;
        margin-bottom: 0.5rem !important;
    }

    /* Cypher expander */
    .cypher-block {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 1rem;
        font-family: 'JetBrains Mono', 'Fira Code', monospace;
        font-size: 0.8rem;
        color: #cdd6f4;
        overflow-x: auto;
        border: 1px solid #313244;
    }

    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8f9ff 0%, #eef1ff 100%);
    }

    .sidebar-card {
        background: white;
        padding: 1rem 1.2rem;
        border-radius: 12px;
        margin-bottom: 0.8rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        border: 1px solid rgba(102, 126, 234, 0.1);
    }
    .sidebar-card h4 {
        margin: 0 0 0.5rem 0;
        color: #4c4f69;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .sidebar-card p {
        margin: 0.2rem 0;
        color: #5c5f77;
        font-size: 0.82rem;
    }

    .stat-number {
        font-size: 1.8rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea, #764ba2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.2;
    }

    /* Example queries */
    .example-btn {
        display: block;
        width: 100%;
        text-align: left;
        padding: 0.6rem 0.8rem;
        margin: 0.3rem 0;
        background: white;
        border: 1px solid #e0e4f2;
        border-radius: 8px;
        color: #4c4f69;
        font-size: 0.78rem;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .example-btn:hover {
        border-color: #667eea;
        background: #f5f3ff;
        transform: translateX(3px);
    }

    /* Status indicator */
    .status-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 6px;
        animation: pulse 2s infinite;
    }
    .status-connected { background: #40a02b; }
    .status-disconnected { background: #d20f39; }

    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
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


# ───────────────────────────────────────────────────────────────────────
# Neo4j Connection
# ───────────────────────────────────────────────────────────────────────

@st.cache_resource
def init_agent():
    """Initialize Neo4j connection and GraphRAG agent."""
    try:
        db = Neo4jManager()
        db.connect()
        agent = GraphRAGAgent(neo4j_manager=db)
        stats = db.get_counts()
        return db, agent, stats, True
    except Exception as e:
        return None, None, None, False


def ensure_connection():
    """Make sure agent is initialized."""
    if not st.session_state.connected:
        db, agent, stats, ok = init_agent()
        st.session_state.db = db
        st.session_state.agent = agent
        st.session_state.graph_stats = stats
        st.session_state.connected = ok


ensure_connection()


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
        st.error("Could not connect to Neo4j. Check your `.env` settings.")

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

    # Example queries
    st.markdown("---")
    st.markdown("#### 💡 Example Queries")

    examples = [
        "Find Python experts with AWS certifications",
        "Who has worked on Banking projects with ML skills?",
        "List employees in Bangalore with Cloud skills",
        "Show top performers in the Data & AI department",
        "Find available people for a project needing Python, Spark, and AWS",
        "Who reports to Priya Rao?",
        "How many employees are in each department?",
        "Find people with Kubernetes training and certification",
    ]

    for ex in examples:
        if st.button(f"💬 {ex}", key=f"ex_{hash(ex)}", use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": ex})
            st.rerun()

    st.markdown("---")

    # Clear chat
    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    # About
    st.markdown(f"""
    <div class="sidebar-card">
        <h4>ℹ️ About</h4>
        <p>OrgGraph AI uses a Neo4j knowledge graph
        with LangGraph agents to answer natural language
        queries about employees, skills, projects,
        certifications, and more.</p>
    </div>
    """, unsafe_allow_html=True)


# ───────────────────────────────────────────────────────────────────────
# Main Content
# ───────────────────────────────────────────────────────────────────────

# Header
st.markdown("""
<div class="main-header">
    <h1>🔍 OrgGraph AI</h1>
    <p>Ask anything about employees, skills, projects, certifications & more</p>
</div>
""", unsafe_allow_html=True)

# Chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧑‍💼" if msg["role"] == "user" else "🤖"):
        st.markdown(msg["content"])

        # Show cypher in expander if available
        if msg["role"] == "assistant" and msg.get("cypher"):
            with st.expander("🔎 View Cypher Query", expanded=False):
                st.code(msg["cypher"], language="cypher")

# Chat input
if prompt := st.chat_input("Ask about employees, skills, projects …"):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💼"):
        st.markdown(prompt)

    # Generate response
    if not st.session_state.connected:
        error_msg = "❌ Not connected to Neo4j. Please check your connection settings."
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
    st.markdown("---")
    cols = st.columns(3)
    cards = [
        ("🎯", "Skill Search", "Find employees by skills, proficiency, and experience"),
        ("📋", "Project Match", "Match people to projects based on requirements"),
        ("🏆", "Performance", "Identify top performers and promotion candidates"),
    ]
    for col, (icon, title, desc) in zip(cols, cards):
        with col:
            st.markdown(f"""
            <div class="sidebar-card" style="text-align: center; padding: 1.5rem;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">{icon}</div>
                <h4 style="text-transform: none; font-size: 1rem;">{title}</h4>
                <p>{desc}</p>
            </div>
            """, unsafe_allow_html=True)
