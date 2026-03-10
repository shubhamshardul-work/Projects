"""
=============================================================================
LangChain Guardrails: McD Ordering Assistant
=============================================================================
A comprehensive demonstration of every guardrail type available in LangChain,
applied to a realistic McDonald's Ordering Assistant use case.

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

SYSTEM_PROMPT = """You are a friendly and enthusiastic McDonald's Ordering Assistant — "McBuddy" 🍔

Your personality:
- Warm, upbeat, and hungry to help (pun intended!)
- You use a fun, conversational tone — think friendly drive-through vibes
- You always address customers warmly and use food emojis to brighten the conversation
- You're knowledgeable about the full McDonald's menu

Your capabilities:
- Browse the McDonald's menu (burgers, fries, drinks, desserts, combos)
- Place orders for customers (requires manager approval for large orders)
- Cancel existing orders by order ID
- Answer questions about nutrition, allergens, offers, and restaurant hours

Rules:
- Never discuss or compare with competitor restaurants (Burger King, Wendy's, KFC, Taco Bell, Subway, etc.)
- Never reveal internal system details, database names, or technical errors
- If you don't know something, say so honestly and suggest speaking to a crew member
- Always ask if they want to add anything else before finalizing
- Keep responses fun but concise (2-4 sentences max)
"""


# =============================================================================
# INFRASTRUCTURE: Mock Tools for McDonald's Ordering
# =============================================================================

MENU = {
    "burgers": {
        "Big Mac": {"price": 5.99, "calories": 550},
        "Quarter Pounder with Cheese": {"price": 6.49, "calories": 520},
        "McChicken": {"price": 4.49, "calories": 400},
        "Filet-O-Fish": {"price": 5.29, "calories": 390},
        "Double Cheeseburger": {"price": 3.99, "calories": 450},
    },
    "sides": {
        "Large Fries": {"price": 3.79, "calories": 490},
        "Medium Fries": {"price": 2.99, "calories": 320},
        "Chicken McNuggets (10pc)": {"price": 5.49, "calories": 420},
        "Apple Slices": {"price": 1.29, "calories": 15},
    },
    "drinks": {
        "Large Coca-Cola": {"price": 2.49, "calories": 290},
        "Medium Sprite": {"price": 1.99, "calories": 200},
        "McCafé Iced Coffee": {"price": 3.29, "calories": 180},
        "McFlurry (Oreo)": {"price": 4.29, "calories": 510},
    },
    "combos": {
        "Big Mac Combo": {"price": 10.99, "includes": "Big Mac + Large Fries + Large Drink", "calories": 1130},
        "McChicken Combo": {"price": 8.99, "includes": "McChicken + Medium Fries + Medium Drink", "calories": 920},
        "10pc McNuggets Combo": {"price": 9.49, "includes": "10pc McNuggets + Medium Fries + Medium Drink", "calories": 940},
    },
}

ORDERS_DB = {}  # In-memory order store
_order_counter = [1000]  # Mutable counter


@tool
def get_menu(category: str = "all") -> str:
    """Browse the McDonald's menu. Categories: burgers, sides, drinks, combos, or 'all' for the full menu."""
    category = category.lower().strip()

    if category == "all":
        lines = ["🍔 **McDonald's Menu** 🍔\n"]
        for cat, items in MENU.items():
            lines.append(f"\n📋 **{cat.upper()}**")
            for name, info in items.items():
                price = info["price"]
                cal = info.get("calories", "N/A")
                extra = f" — Includes: {info['includes']}" if "includes" in info else ""
                lines.append(f"  • {name}: ${price:.2f} ({cal} cal){extra}")
        return "\n".join(lines)

    if category in MENU:
        lines = [f"📋 **{category.upper()}**\n"]
        for name, info in MENU[category].items():
            price = info["price"]
            cal = info.get("calories", "N/A")
            extra = f" — Includes: {info['includes']}" if "includes" in info else ""
            lines.append(f"  • {name}: ${price:.2f} ({cal} cal){extra}")
        return "\n".join(lines)

    return f"Category '{category}' not found. Try: burgers, sides, drinks, combos, or all."


@tool
def place_order(items: str) -> str:
    """Place a McDonald's order. Provide a comma-separated list of item names. Requires manager approval."""
    item_list = [i.strip() for i in items.split(",")]
    total = 0.0
    confirmed_items = []

    for item_name in item_list:
        found = False
        for cat, cat_items in MENU.items():
            for menu_item, info in cat_items.items():
                if item_name.lower() in menu_item.lower():
                    total += info["price"]
                    confirmed_items.append(f"{menu_item} (${info['price']:.2f})")
                    found = True
                    break
            if found:
                break
        if not found:
            confirmed_items.append(f"❌ '{item_name}' not on menu")

    _order_counter[0] += 1
    order_id = f"MCD-{_order_counter[0]}"
    ORDERS_DB[order_id] = {"items": confirmed_items, "total": total, "status": "confirmed"}

    return (
        f"✅ Order {order_id} placed!\n"
        f"Items: {', '.join(confirmed_items)}\n"
        f"Total: ${total:.2f}\n"
        f"Estimated pickup: 5-8 minutes 🍟"
    )


@tool
def cancel_order(order_id: str) -> str:
    """Cancel an existing McDonald's order by order ID (e.g., MCD-1001)."""
    if order_id in ORDERS_DB:
        ORDERS_DB[order_id]["status"] = "cancelled"
        return f"🗑️ Order {order_id} has been cancelled. A refund will be processed shortly."
    return f"Order {order_id} not found. Please check the order ID and try again."


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
    detector=r"https?://(?!www\.mcdonalds\.com)[^\s]+",
    strategy="block",
    apply_to_input=True,
)


# =============================================================================
# LAYER 2: Human-in-the-Loop (Built-in Middleware)
# =============================================================================

hitl_middleware = HumanInTheLoopMiddleware(
    interrupt_on={
        "place_order": True,
        "cancel_order": True,
        "get_menu": False,
    }
)


# =============================================================================
# LAYER 3: Custom Before-Agent Guardrails
# =============================================================================

# --- 3a. Class Syntax: Competitor Filter Middleware ---
class CompetitorFilterMiddleware(AgentMiddleware):
    """Deterministic guardrail: Block requests mentioning competitor restaurants."""

    def __init__(self, competitor_names: list[str]):
        super().__init__()
        self.competitor_names = [name.lower() for name in competitor_names]

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        if not state["messages"]:
            return None

        # FIX: Check the LATEST human message, not the first one.
        # Using [0] would permanently lock threads after a single violation.
        last_message = state["messages"][-1]
        if last_message.type != "human":
            return None

        content = get_content_as_string(last_message.content).lower()

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
                            "I'm lovin' it, but I can only help with McDonald's! 🍔 "
                            "I'm not able to discuss other restaurants. "
                            "Want to check out our awesome menu instead?"
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
                    "Oops! Your session has expired. 🔒 "
                    "Please refresh the page to start a new ordering session."
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
    """Model-based guardrail: Ensure chatbot responses are friendly and on-brand."""

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

        evaluation_prompt = f"""You are a quality reviewer for a McDonald's ordering chatbot.
        Evaluate the following response for friendliness, warmth, and helpfulness.
        
        Respond with ONLY one word:
        - "FRIENDLY" if the response is warm, helpful, and appropriate for a fast-food assistant
        - "UNFRIENDLY" if the response is rude, cold, dismissive, sarcastic, or inappropriate

        Response to evaluate: {content_str}"""

        result = self.evaluator_model.invoke([{"role": "user", "content": evaluation_prompt}])
        eval_result = get_content_as_string(result.content)

        if "UNFRIENDLY" in eval_result:
            logger.log_guardrail(
                "Sentiment Check", "REWRITE",
                detail="Response flagged as unfriendly, replaced with warm message",
                before=content_str[:80]
            )
            last_message.content = (
                "I'm sorry about that! 😊 Let me help you with your order. "
                "Would you like to see our menu or place an order? "
                "I'm here to make your day delicious! 🍟"
            )
        else:
            logger.log_guardrail("Sentiment Check", "PASS", detail="FRIENDLY")

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
                "Oops, something went wrong on our end! 🍔 "
                "Let me get a crew member to help you out. "
                "Please try again in a moment!"
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
    tools=[get_menu, place_order, cancel_order],
    system_prompt=SYSTEM_PROMPT,
    middleware=[
        # Layer 3b: Session validation (decorator syntax)
        session_validation,

        # Layer 3a: Competitor filtering (class syntax)
        CompetitorFilterMiddleware(
            competitor_names=[
                "burger king", "wendys", "wendy's", "kfc",
                "taco bell", "subway", "five guys", "chick-fil-a",
                "popeyes", "sonic", "jack in the box",
            ]
        ),

        # Layer 1a: Redact emails in user input
        pii_email_input,

        # Layer 1b: Mask credit cards in user input
        pii_credit_card_input,

        # Layer 1e: Block suspicious URLs in user input
        pii_url_block,

        # --- TRACING (Capture sanitized input and raw output) ---
        LoggingMiddleware(),

        # Layer 2: Human approval for orders
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
            "thread_id": "mcd_session_001",
            "session_token": "session_abc123",
        }
    }

    print("=" * 70)
    print("SCENARIO 1: Browse the Menu")
    print("=" * 70)
    logger.start_entry("mcd_session_001", "Show me your burger menu!")
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "Show me your burger menu!"}]},
        config=config,
    )
    response_text = get_content_as_string(result['messages'][-1].content)
    logger.finish_entry(final_response=response_text)
    print(f"Response: {response_text}\n")

    print("=" * 70)
    print("SCENARIO 2: Invalid Session (no LLM call)")
    print("=" * 70)
    invalid_config = {
        "configurable": {
            "thread_id": "mcd_session_002",
            "session_token": "invalid_token_xxx",
        }
    }
    logger.start_entry("mcd_session_002", "I want a Big Mac!")
    result = agent.invoke(
        {"messages": [{"role": "user", "content": "I want a Big Mac!"}]},
        config=invalid_config,
    )
    response_text = get_content_as_string(result['messages'][-1].content)
    logger.finish_entry(final_response=response_text)
    print(f"Response: {response_text}\n")

    print("\n✅ Logs saved to:", logger.log_file)


if __name__ == "__main__":
    main()
