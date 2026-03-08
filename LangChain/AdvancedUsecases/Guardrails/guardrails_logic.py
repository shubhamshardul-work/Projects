"""
=============================================================================
LangChain Guardrails: Customer Support Chatbot
=============================================================================
A comprehensive demonstration of every guardrail type available in LangChain,
applied to a realistic Customer Support Chatbot use case.

Guardrail Layers:
    Layer 1 - PII Detection (Built-in middleware)
    Layer 2 - Human-in-the-Loop (Built-in middleware)
    Layer 3 - Custom Before-Agent Guardrails (Class & Decorator syntax)
    Layer 4 - Custom After-Agent Guardrails (Class & Decorator syntax)
=============================================================================
"""

from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    PIIMiddleware,
    HumanInTheLoopMiddleware,
    AgentMiddleware,
    AgentState,
    hook_config,
    before_agent,
    after_agent,
)
from langchain.chat_models import init_chat_model
from langchain.messages import AIMessage
from langchain.tools import tool
from langgraph.config import get_config
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime
from langgraph.types import Command
import os
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv(dotenv_path="/Users/shardulmac/Documents/Projects/Projects/.env")

# =============================================================================
# INFRASTRUCTURE: Mock Tools for Customer Support Chatbot
# =============================================================================

@tool
def check_order_status(order_id: str) -> str:
    """Check the status of a customer's order by order ID."""
    # Simulated order database
    orders = {
        "ORD-1234": "Shipped - Expected delivery: March 12, 2026",
        "ORD-5678": "Processing - Preparing for shipment",
        "ORD-9999": "Delivered - March 5, 2026",
    }
    return orders.get(order_id, f"Order {order_id} not found in our system.")


@tool
def initiate_refund(order_id: str, reason: str) -> str:
    """Initiate a refund for a customer's order. Requires human approval."""
    return f"Refund initiated for order {order_id}. Reason: {reason}. Amount will be credited in 5-7 business days."


@tool
def search_knowledge_base(query: str) -> str:
    """Search the internal knowledge base for customer support articles."""
    # Simulated knowledge base
    articles = {
        "return policy": "Items can be returned within 30 days of purchase. Electronics have a 15-day return window.",
        "shipping": "Standard shipping: 5-7 days. Express: 2-3 days. Free shipping on orders over $50.",
        "warranty": "All products come with a 1-year manufacturer warranty. Extended warranties available for purchase.",
    }
    for keyword, article in articles.items():
        if keyword in query.lower():
            return article
    return "No relevant articles found. Please contact a human agent for assistance."


# =============================================================================
# LAYER 1: PII Detection (Built-in Middleware)
# =============================================================================
# Demonstrates all 5 built-in PII types and all 4 strategies.
# Each middleware instance protects a different data type at a different point.

# --- 1a. Email Detection: REDACT strategy on INPUT ---
# Protects customer emails from being sent to the model
pii_email_input = PIIMiddleware(
    "email",
    strategy="redact",
    apply_to_input=True,
)

# --- 1b. Credit Card Detection: MASK strategy on INPUT ---
# Partially masks credit card numbers (shows last 4 digits)
pii_credit_card_input = PIIMiddleware(
    "credit_card",
    strategy="mask",
    apply_to_input=True,
)

# --- 1c. IP Address Detection: HASH strategy on TOOL RESULTS ---
# Hashes any IP addresses returned by internal tools
pii_ip_tool_results = PIIMiddleware(
    "ip",
    strategy="hash",
    apply_to_tool_results=True,
)

# --- 1d. MAC Address Detection: REDACT strategy on OUTPUT ---
# Prevents the model from leaking internal system MAC addresses
pii_mac_output = PIIMiddleware(
    "mac_address",
    strategy="redact",
    apply_to_output=True,
)

# --- 1e. URL Detection: BLOCK strategy with custom detector on INPUT ---
# Blocks messages containing suspicious or phishing-like URLs
pii_url_block = PIIMiddleware(
    "url",
    detector=r"https?://(?!www\.ourcompany\.com)[^\s]+",  # Block all non-company URLs
    strategy="block",
    apply_to_input=True,
)


# =============================================================================
# LAYER 2: Human-in-the-Loop (Built-in Middleware)
# =============================================================================
# Requires a support agent to approve high-risk actions like refunds,
# while auto-approving safe operations like searching or checking status.

hitl_middleware = HumanInTheLoopMiddleware(
    interrupt_on={
        # Require human approval for financial operations
        "initiate_refund": True,
        # Auto-approve safe, read-only operations
        "check_order_status": False,
        "search_knowledge_base": False,
    }
)


# =============================================================================
# LAYER 3: Custom Before-Agent Guardrails
# =============================================================================
# These run ONCE at the start of each invocation, before any processing.
# Useful for session-level checks: authentication, rate limiting, content filtering.

# --- 3a. Class Syntax: Competitor Filter Middleware ---
# Blocks customer messages that mention competitor companies.

class CompetitorFilterMiddleware(AgentMiddleware):
    """Deterministic guardrail: Block requests mentioning competitor companies."""

    def __init__(self, competitor_names: list[str]):
        super().__init__()
        self.competitor_names = [name.lower() for name in competitor_names]

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        if not state["messages"]:
            return None

        first_message = state["messages"][0]
        if first_message.type != "human":
            return None

        content = first_message.content.lower()

        for competitor in self.competitor_names:
            if competitor in content:
                return {
                    "messages": [{
                        "role": "assistant",
                        "content": (
                            "I appreciate your question! However, I can only assist with "
                            "questions about our own products and services. Is there anything "
                            "else I can help you with today?"
                        ),
                    }],
                    "jump_to": "end",
                }

        return None


# --- 3b. Decorator Syntax: Session Validation Middleware ---
# Validates that the customer has a valid session before processing requests.

VALID_SESSION_TOKENS = {"session_abc123", "session_xyz789", "session_demo"}


@before_agent(can_jump_to=["end"])
def session_validation(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """Deterministic guardrail: Validate user session before processing."""
    # Use get_config() from langgraph.config (the official way per Runtime docs)
    config = get_config()
    session_token = config.get("configurable", {}).get("session_token")

    if not session_token or session_token not in VALID_SESSION_TOKENS:
        return {
            "messages": [{
                "role": "assistant",
                "content": (
                    "Your session has expired or is invalid. "
                    "Please log in again to continue using our support chat."
                ),
            }],
            "jump_to": "end",
        }

    return None


# =============================================================================
# LAYER 4: Custom After-Agent Guardrails
# =============================================================================
# These run ONCE after the agent completes, before returning to the user.
# Useful for final safety checks, quality validation, and compliance scans.

# --- 4a. Class Syntax: Sentiment Guardrail Middleware ---
# Uses a secondary LLM to evaluate if the chatbot's response is professional.

class SentimentGuardrailMiddleware(AgentMiddleware):
    """Model-based guardrail: Ensure chatbot responses are professional and polite."""

    def __init__(self):
        super().__init__()
        self.evaluator_model = ChatGoogleGenerativeAI(model="models/gemini-flash-latest")

    @hook_config(can_jump_to=["end"])
    def after_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        if not state["messages"]:
            return None

        last_message = state["messages"][-1]
        if not isinstance(last_message, AIMessage):
            return None

        # Use a model to evaluate tone and professionalism
        evaluation_prompt = f"""You are a quality assurance reviewer for a customer support chatbot.
        Evaluate the following response for professionalism, politeness, and helpfulness.
        
        Respond with ONLY one word:
        - "PROFESSIONAL" if the response is appropriate for customer support
        - "UNPROFESSIONAL" if the response is rude, dismissive, sarcastic, or inappropriate

        Response to evaluate: {last_message.content}"""

        result = self.evaluator_model.invoke([{"role": "user", "content": evaluation_prompt}])

        if "UNPROFESSIONAL" in result.content:
            last_message.content = (
                "I apologize for the inconvenience. Let me connect you with a human "
                "support agent who can better assist you with your request. "
                "Thank you for your patience!"
            )

        return None


# --- 4b. Decorator Syntax: Response Validation Middleware ---
# Ensures no internal technical jargon or system details leak to customers.

BLOCKED_TERMS = [
    "internal_id",
    "db_connection",
    "stack_trace",
    "traceback",
    "NoneType",
    "AttributeError",
    "KeyError",
    "Exception(",
    "SELECT * FROM",
    "DROP TABLE",
]


@after_agent(can_jump_to=["end"])
def response_validation(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """Deterministic guardrail: Ensure no technical jargon leaks to customers."""
    if not state["messages"]:
        return None

    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage):
        return None

    content = last_message.content

    for term in BLOCKED_TERMS:
        if term.lower() in content.lower():
            last_message.content = (
                "I encountered an issue processing your request. "
                "Let me connect you with a specialist who can help. "
                "Thank you for your patience!"
            )
            return None

    return None


# =============================================================================
# AGENT CREATION: Stacking All Guardrail Layers
# =============================================================================
# Middleware executes in order. This creates a layered defense:
#   1. Session validation (before agent)
#   2. Competitor filtering (before agent)
#   3. PII protection on input (before model)
#   4. Human approval for sensitive tools (around tool calls)
#   5. PII protection on tool results (after tool)
#   6. PII protection on output (after model)
# Initialize the Gemini model for the agent
agent_model = ChatGoogleGenerativeAI(model="models/gemini-flash-latest")

agent = create_agent(
    model=agent_model,
    tools=[check_order_status, initiate_refund, search_knowledge_base],
    middleware=[
        # Layer 3a: Session validation (decorator syntax - before agent)
        session_validation,

        # Layer 3b: Competitor filtering (class syntax - before agent)
        CompetitorFilterMiddleware(
            competitor_names=["competitor_x", "rival_corp", "other_brand"]
        ),

        # Layer 1a: Redact emails in user input
        pii_email_input,

        # Layer 1b: Mask credit cards in user input
        pii_credit_card_input,

        # Layer 1e: Block suspicious URLs in user input
        pii_url_block,

        # Layer 2: Human approval for refunds
        hitl_middleware,

        # Layer 1c: Hash IP addresses in tool results
        pii_ip_tool_results,

        # Layer 1d: Redact MAC addresses in model output
        pii_mac_output,

        # Layer 4a: Sentiment check on final response (class syntax)
        SentimentGuardrailMiddleware(),

        # Layer 4b: Technical jargon filter (decorator syntax)
        response_validation,
    ],
    # Required for human-in-the-loop persistence
    checkpointer=InMemorySaver(),
)


# =============================================================================
# EXAMPLE INVOCATIONS: Testing Each Guardrail
# =============================================================================

def main():
    """Run example scenarios to demonstrate each guardrail layer."""

    # Thread config with valid session for normal operation
    config = {
        "configurable": {
            "thread_id": "customer_session_001",
            "session_token": "session_abc123",
        }
    }

    # -------------------------------------------------------------------------
    # Scenario 1: Normal query (passes all guardrails)
    # -------------------------------------------------------------------------
    print("=" * 70)
    print("SCENARIO 1: Normal Query")
    print("=" * 70)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "What is your return policy?"}]},
        config=config,
    )
    print(f"Response: {result['messages'][-1].content}\n")

    # -------------------------------------------------------------------------
    # Scenario 2: PII Detection - Email & Credit Card (Layer 1a, 1b)
    # -------------------------------------------------------------------------
    print("=" * 70)
    print("SCENARIO 2: PII Detection (Email + Credit Card)")
    print("=" * 70)
    config_2 = {
        "configurable": {
            "thread_id": "customer_session_002",
            "session_token": "session_abc123",
        }
    }
    result = agent.invoke(
        {
            "messages": [{
                "role": "user",
                "content": (
                    "My email is jane.doe@example.com and my card is "
                    "4111-1111-1111-1234. Can you check order ORD-1234?"
                ),
            }]
        },
        config=config_2,
    )
    print(f"Response: {result['messages'][-1].content}\n")

    # -------------------------------------------------------------------------
    # Scenario 3: URL Blocking (Layer 1e)
    # -------------------------------------------------------------------------
    print("=" * 70)
    print("SCENARIO 3: Suspicious URL Blocking")
    print("=" * 70)
    config_3 = {
        "configurable": {
            "thread_id": "customer_session_003",
            "session_token": "session_abc123",
        }
    }
    try:
        result = agent.invoke(
            {
                "messages": [{
                    "role": "user",
                    "content": "Check this link: https://phishing-site.com/steal-data",
                }]
            },
            config=config_3,
        )
        print(f"Response: {result['messages'][-1].content}\n")
    except Exception as e:
        print(f"Blocked! Error: {e}\n")

    # -------------------------------------------------------------------------
    # Scenario 4: Competitor Mention Filter (Layer 3a - Class syntax)
    # -------------------------------------------------------------------------
    print("=" * 70)
    print("SCENARIO 4: Competitor Filter (Before-Agent, Class Syntax)")
    print("=" * 70)
    config_4 = {
        "configurable": {
            "thread_id": "customer_session_004",
            "session_token": "session_abc123",
        }
    }
    result = agent.invoke(
        {
            "messages": [{
                "role": "user",
                "content": "How does your product compare to Competitor_X?",
            }]
        },
        config=config_4,
    )
    print(f"Response: {result['messages'][-1].content}\n")

    # -------------------------------------------------------------------------
    # Scenario 5: Invalid Session (Layer 3b - Decorator syntax)
    # -------------------------------------------------------------------------
    print("=" * 70)
    print("SCENARIO 5: Session Validation (Before-Agent, Decorator Syntax)")
    print("=" * 70)
    invalid_config = {
        "configurable": {
            "thread_id": "customer_session_005",
            "session_token": "invalid_token_xxx",
        }
    }
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "I need help with my order."}]},
        config=invalid_config,
    )
    print(f"Response: {result['messages'][-1].content}\n")

    # -------------------------------------------------------------------------
    # Scenario 6: Human-in-the-Loop for Refunds (Layer 2)
    # -------------------------------------------------------------------------
    print("=" * 70)
    print("SCENARIO 6: Human-in-the-Loop (Refund Approval)")
    print("=" * 70)
    config_6 = {
        "configurable": {
            "thread_id": "customer_session_006",
            "session_token": "session_abc123",
        }
    }

    # Step 1: Request triggers interrupt
    result = agent.invoke(
        {
            "messages": [{
                "role": "user",
                "content": "I want a refund for order ORD-5678. The item was damaged.",
            }]
        },
        config=config_6,
    )
    print(f"Agent paused for approval. Current state: {result['messages'][-1].content}")

    # Step 2: Human agent approves the refund
    result = agent.invoke(
        Command(resume={"decisions": [{"type": "approve"}]}),
        config=config_6,
    )
    print(f"After approval: {result['messages'][-1].content}\n")


if __name__ == "__main__":
    main()
