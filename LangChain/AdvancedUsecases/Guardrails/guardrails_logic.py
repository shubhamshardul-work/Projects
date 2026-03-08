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
import json
import os
import time
from datetime import datetime
from pathlib import Path

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
from langchain.messages import AIMessage, HumanMessage, SystemMessage
from langchain.tools import tool
from langgraph.config import get_config
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime
from langgraph.types import Command
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv(dotenv_path="/Users/shardulmac/Documents/Projects/Projects/.env")


# =============================================================================
# UTILITIES
# =============================================================================

def get_content_as_string(content: Any) -> str:
    """Convert message content (str or list) to a normalized string.
    Gemini often returns content as a list of dicts like [{"text": "..."}]
    instead of a plain string. This helper normalizes both formats.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                text_parts.append(item.get("text", ""))
            elif isinstance(item, str):
                text_parts.append(item)
            else:
                text_parts.append(str(item))
        return " ".join(text_parts)
    return str(content)


# =============================================================================
# CONVERSATION LOGGER
# =============================================================================
# Structured JSON logging that captures every guardrail action at each stage.

LOG_DIR = Path(__file__).parent / "guardrails_logs"
LOG_DIR.mkdir(exist_ok=True)


class ConversationLogger:
    """Logs every interaction with full guardrail pipeline details to JSON."""

    def __init__(self):
        self.log_file = LOG_DIR / "conversation_log.jsonl"
        self._current_entry = None

    def start_entry(self, thread_id: str, user_input: str):
        """Begin a new log entry for an incoming user message."""
        self._current_entry = {
            "timestamp": datetime.now().isoformat(),
            "thread_id": thread_id,
            "user_input_raw": user_input,
            "llm_input": None,          # What actually went to the LLM (post-PII)
            "llm_raw_output": None,     # What the LLM returned (pre-validation)
            "guardrails_pipeline": [],
            "final_response": None,
            "error": None,
        }

    def log_guardrail(self, stage: str, action: str, detail: str = None,
                      before: str = None, after: str = None):
        """Record a guardrail action (PASS, BLOCK, REDACT, MASK, etc.)."""
        if self._current_entry is None:
            return
        entry = {"stage": stage, "action": action}
        if detail:
            entry["detail"] = detail
        if before:
            entry["before"] = before[:100]  # Truncate for log size
        if after:
            entry["after"] = after[:100]
        self._current_entry["guardrails_pipeline"].append(entry)

    def finish_entry(self, final_response: str = None, error: str = None):
        """Finalize and write the log entry to disk."""
        if self._current_entry is None:
            return
        self._current_entry["final_response"] = final_response
        self._current_entry["error"] = error
        with open(self.log_file, "a") as f:
            f.write(json.dumps(self._current_entry, ensure_ascii=False) + "\n")
        self._current_entry = None

    def get_all_logs(self) -> list[dict]:
        """Read all log entries from the log file."""
        logs = []
        if self.log_file.exists():
            with open(self.log_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        logs.append(json.loads(line))
        return logs


# Global logger instance
logger = ConversationLogger()


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = """You are a friendly and professional Customer Support Assistant for "ShieldTech Solutions", a premium electronics and gadgets company.

Your personality:
- Warm, empathetic, and solution-oriented
- You address customers by "you" and use a conversational but professional tone
- You never use jargon or overly technical language
- You always try to resolve the issue or guide the customer to the right resource

Your capabilities:
- Check order status using order IDs (format: ORD-XXXX)
- Initiate refunds for damaged or defective products (requires supervisor approval)
- Search the knowledge base for policies (returns, shipping, warranty)

Rules:
- Never reveal internal system details, database names, or technical errors
- If you don't know something, say so honestly and point the customer to a human agent
- Always end with an offer to help further
- Keep responses concise but helpful (2-4 sentences max)
"""


# =============================================================================
# INFRASTRUCTURE: Mock Tools for Customer Support Chatbot
# =============================================================================

@tool
def check_order_status(order_id: str) -> str:
    """Check the status of a customer's order by order ID."""
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
    articles = {
        "return policy": "Items can be returned within 30 days of purchase. Electronics have a 15-day return window. Items must be in original packaging.",
        "shipping": "Standard shipping: 5-7 business days. Express: 2-3 business days. Free shipping on orders over $50.",
        "warranty": "All products come with a 1-year manufacturer warranty. Extended warranties are available for purchase at checkout.",
        "refund": "Refunds are processed within 5-7 business days after approval. The amount is credited to the original payment method.",
        "contact": "You can reach our support team at support@shieldtech.com or call 1-800-SHIELD-TECH.",
    }
    for keyword, article in articles.items():
        if keyword in query.lower():
            return article
    return "No relevant articles found. A human agent can assist you further."


# =============================================================================
# LAYER 1: PII Detection (Built-in Middleware)
# =============================================================================

# --- 1a. Email Detection: REDACT strategy on INPUT ---
pii_email_input = PIIMiddleware(
    "email",
    strategy="redact",
    apply_to_input=True,
)

# --- 1b. Credit Card Detection: MASK strategy on INPUT ---
pii_credit_card_input = PIIMiddleware(
    "credit_card",
    strategy="mask",
    apply_to_input=True,
)

# --- 1c. IP Address Detection: HASH strategy on TOOL RESULTS ---
pii_ip_tool_results = PIIMiddleware(
    "ip",
    strategy="hash",
    apply_to_tool_results=True,
)

# --- 1d. MAC Address Detection: REDACT strategy on OUTPUT ---
pii_mac_output = PIIMiddleware(
    "mac_address",
    strategy="redact",
    apply_to_output=True,
)

# --- 1e. URL Detection: BLOCK strategy with custom detector on INPUT ---
pii_url_block = PIIMiddleware(
    "url",
    detector=r"https?://(?!www\.ourcompany\.com)[^\s]+",
    strategy="block",
    apply_to_input=True,
)


# =============================================================================
# LAYER 2: Human-in-the-Loop (Built-in Middleware)
# =============================================================================

hitl_middleware = HumanInTheLoopMiddleware(
    interrupt_on={
        "initiate_refund": True,
        "check_order_status": False,
        "search_knowledge_base": False,
    }
)


# =============================================================================
# LAYER 3: Custom Before-Agent Guardrails
# =============================================================================

# --- 3a. Class Syntax: Competitor Filter Middleware ---
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

        content = get_content_as_string(first_message.content).lower()

        for competitor in self.competitor_names:
            if competitor in content:
                logger.log_guardrail(
                    "Competitor Filter", "BLOCK",
                    detail=f"Blocked mention of '{competitor}'"
                )
                return {
                    "messages": [{
                        "role": "assistant",
                        "content": (
                            "I appreciate your question! However, I can only assist with "
                            "questions about our own products and services at ShieldTech. "
                            "Is there anything else I can help you with today?"
                        ),
                    }],
                    "jump_to": "end",
                }

        logger.log_guardrail("Competitor Filter", "PASS")
        return None


# --- 3b. Decorator Syntax: Session Validation Middleware ---
VALID_SESSION_TOKENS = {"session_abc123", "session_xyz789", "session_demo"}


@before_agent(can_jump_to=["end"])
def session_validation(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """Deterministic guardrail: Validate user session before processing."""
    config = get_config()
    session_token = config.get("configurable", {}).get("session_token")

    if not session_token or session_token not in VALID_SESSION_TOKENS:
        logger.log_guardrail(
            "Session Validation", "BLOCK",
            detail=f"Invalid token: {session_token or 'missing'}"
        )
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

    logger.log_guardrail("Session Validation", "PASS", detail="Valid token")
    return None


# =============================================================================
# LAYER 4: Custom After-Agent Guardrails
# =============================================================================

# --- 4a. Class Syntax: Sentiment Guardrail Middleware ---
class SentimentGuardrailMiddleware(AgentMiddleware):
    """Model-based guardrail: Ensure chatbot responses are professional and polite."""

    def __init__(self):
        super().__init__()
        self.evaluator_model = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

    @hook_config(can_jump_to=["end"])
    def after_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        if not state["messages"]:
            return None

        last_message = state["messages"][-1]
        if not isinstance(last_message, AIMessage):
            return None

        content_str = get_content_as_string(last_message.content)

        evaluation_prompt = f"""You are a quality assurance reviewer for a customer support chatbot.
        Evaluate the following response for professionalism, politeness, and helpfulness.
        
        Respond with ONLY one word:
        - "PROFESSIONAL" if the response is appropriate for customer support
        - "UNPROFESSIONAL" if the response is rude, dismissive, sarcastic, or inappropriate

        Response to evaluate: {content_str}"""

        result = self.evaluator_model.invoke([{"role": "user", "content": evaluation_prompt}])
        eval_result = get_content_as_string(result.content)

        if "UNPROFESSIONAL" in eval_result:
            logger.log_guardrail(
                "Sentiment Check", "REWRITE",
                detail="Response flagged as unprofessional, replaced with apology",
                before=content_str[:80]
            )
            last_message.content = (
                "I apologize for the inconvenience. Let me connect you with a human "
                "support agent who can better assist you with your request. "
                "Thank you for your patience!"
            )
        else:
            logger.log_guardrail("Sentiment Check", "PASS", detail="PROFESSIONAL")

        return None


# --- 4b. Decorator Syntax: Response Validation Middleware ---
BLOCKED_TERMS = [
    "internal_id", "db_connection", "stack_trace", "traceback",
    "NoneType", "AttributeError", "KeyError", "Exception(",
    "SELECT * FROM", "DROP TABLE",
]


@after_agent(can_jump_to=["end"])
def response_validation(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """Deterministic guardrail: Ensure no technical jargon leaks to customers."""
    if not state["messages"]:
        return None

    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage):
        return None

    content = get_content_as_string(last_message.content)

    for term in BLOCKED_TERMS:
        if term.lower() in content.lower():
            logger.log_guardrail(
                "Response Validation", "REWRITE",
                detail=f"Blocked term detected: '{term}'",
                before=content[:80]
            )
            last_message.content = (
                "I encountered an issue processing your request. "
                "Let me connect you with a specialist who can help. "
                "Thank you for your patience!"
            )
            return None

    logger.log_guardrail("Response Validation", "PASS")
    return None


# =============================================================================
# TRACING MIDDLEWARE (To capture built-in PII effects)
# =============================================================================

class LoggingMiddleware(AgentMiddleware):
    """Hooks right before and after the LLM call to capture complete traces.
    This allows us to see the exact input the LLM receives (after built-in PII 
    middlewares modify it) and the raw output it produces.
    """
    
    @hook_config(can_jump_to=["end"])
    def before_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        if not state["messages"]:
            return None
            
        last_msg = state["messages"][-1]
        
        # Capture the modified payload going to the LLM
        if last_msg.type == "human":
            llm_input = get_content_as_string(last_msg.content)
            
            if logger._current_entry:
                logger._current_entry["llm_input"] = llm_input
                original_input = logger._current_entry.get("user_input_raw", "")
                
                # If the input was modified by built-in PII middlewares, log it!
                if llm_input != original_input and original_input:
                    logger.log_guardrail(
                        "Built-in PII Middlewares", "MODIFIED",
                        detail="Input payload was sanitized before reaching LLM",
                        before=original_input[:100],
                        after=llm_input[:100]
                    )
        return None

    @hook_config(can_jump_to=["end"])
    def after_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        if not state["messages"]:
            return None
            
        last_msg = state["messages"][-1]
        
        # Capture the raw output coming back from the LLM
        if last_msg.type == "ai":
            if logger._current_entry:
                logger._current_entry["llm_raw_output"] = get_content_as_string(last_msg.content)
                
        return None


# =============================================================================
# AGENT CREATION: Stacking All Guardrail Layers
# =============================================================================

agent_model = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.3,
)

agent = create_agent(
    model=agent_model,
    tools=[check_order_status, initiate_refund, search_knowledge_base],
    system_prompt=SYSTEM_PROMPT,
    middleware=[
        # --- TRACING (Wraps the LLM to capture inputs/outputs) ---
        LoggingMiddleware(),
        
        # Layer 3b: Session validation (decorator syntax)
        session_validation,

        # Layer 3a: Competitor filtering (class syntax)
        CompetitorFilterMiddleware(
            competitor_names=[
                "competitor_x", "rival_corp", "other_brand",
                "singh corps", "techzone", "gadgetworld",
            ]
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
    checkpointer=InMemorySaver(),
)


# =============================================================================
# EXAMPLE INVOCATIONS (for standalone testing only)
# =============================================================================

def main():
    """Run example scenarios to demonstrate each guardrail layer."""

    config = {
        "configurable": {
            "thread_id": "customer_session_001",
            "session_token": "session_abc123",
        }
    }

    print("=" * 70)
    print("SCENARIO 1: Normal Query")
    print("=" * 70)
    logger.start_entry("customer_session_001", "What is your return policy?")
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "What is your return policy?"}]},
        config=config,
    )
    response_text = get_content_as_string(result['messages'][-1].content)
    logger.finish_entry(final_response=response_text)
    print(f"Response: {response_text}\n")

    print("=" * 70)
    print("SCENARIO 5: Invalid Session (no LLM call)")
    print("=" * 70)
    invalid_config = {
        "configurable": {
            "thread_id": "customer_session_005",
            "session_token": "invalid_token_xxx",
        }
    }
    logger.start_entry("customer_session_005", "I need help with my order.")
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "I need help with my order."}]},
        config=invalid_config,
    )
    response_text = get_content_as_string(result['messages'][-1].content)
    logger.finish_entry(final_response=response_text)
    print(f"Response: {response_text}\n")

    print("\n✅ Logs saved to:", logger.log_file)


if __name__ == "__main__":
    main()
