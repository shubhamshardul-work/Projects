# Securing GenAI: A Practical Guide to Building AI Guardrails with LangChain 🛡️🍔

*How to keep your Large Language Models safe, compliant, and on-brand, featuring a step-by-step tutorial on building "McBuddy" — a fully-railed AI ordering assistant.*

---

Large Language Models (LLMs) are incredibly powerful, but putting them directly in front of your customers without safety nets is like letting a teenager drive a Ferrari with no brakes. They might get to the destination perfectly, or they might veer off course, leak sensitive data, or accidentally praise your biggest competitor.

As companies move from AI prototypes to production, a new critical requirement has emerged: **Guardrails**. 

In this article, we'll explore what guardrails are, why you need them, and walk through a step-by-step implementation of a production-ready guardrail architecture using LangChain's `AgentMiddleware`.

---

## What Are AI Guardrails?

AI Guardrails are the boundaries, filters, and safety checks placed around an LLM to control its inputs and outputs. They act as automated "bouncers" that intercept requests and responses to ensure the AI behaves within defined corporate, legal, and ethical parameters.

### Why Do We Need Them? (Core Use Cases)

If you're building customer-facing AI, you need guardrails for:

1.  **Data Privacy (PII Protection):** Preventing users from exposing sensitive information (emails, credit cards, SSNs) to third-party LLM inference APIs.
2.  **Brand Safety & Competitor Filtering:** Stopping your AI from recommending a competitor's product or discussing unauthorized off-brand topics.
3.  **Human-in-the-Loop (HITL) for High-Stakes Actions:** Pausing execution before an AI performs a critical function (like placing an order, issuing a refund, or sending an email) so a human can approve it.
4.  **Tone & Sentiment Control:** Guaranteeing the bot remains polite, helpful, and never hallucinates rude or inappropriate responses.
5.  **Protection Against Prompt Injection:** Stopping malicious users from overriding the bot's system instructions.

---

## Building "McBuddy": A Step-by-Step Implementation

To make this practical, let's build something real. We are going to build **McBuddy**, an AI ordering assistant for McDonald's that can browse the menu and place orders.

We'll use **LangChain** and its powerful `AgentMiddleware` to implement a multi-layered guardrail architecture.

### Step 1: Setting up the Base Agent
First, we define our LLM, our tools (menu browsing, order placement), and the system prompt.

```python
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent

# Initialize the LLM
agent_model = init_chat_model("gemini-2.5-flash")

# Define our tools
tools = [get_menu, place_order, cancel_order]

SYSTEM_PROMPT = """You are McBuddy, a friendly McDonald's Ordering Assistant 🍔. 
Be warm, upbeat, and knowledgeable about our menu."""
```

If we stopped here, McBuddy could easily be tricked into ordering a Whopper or leaking a user's credit card. Let's add the rails.

---

### Step 2: Layer 1 — Protecting Customer Data (PII Middleware)
Customers often overshare. A user might say, *"I want a Big Mac, and my email is john@doe.com for the receipt."* We don't want that email hitting the LLM. LangChain provides native `PIIMiddleware`.

```python
from langchain.agents.middleware import PIIMiddleware

# Redact emails in user input before it hits the LLM
pii_email_input = PIIMiddleware(
    "email",
    strategy="redact",
    apply_to_input=True,
)

# Mask credit cards (shows only last 4 digits)
pii_credit_card_input = PIIMiddleware(
    "credit_card",
    strategy="mask",
    apply_to_input=True,
)
```
Now, when a user types an email, the LLM only ever sees `[REDACTED_EMAIL]`.

---

### Step 3: Layer 2 — Competitor Filtering (Before-Agent Middleware)
Fast food is fiercely competitive. We absolutely cannot have McBuddy discussing other restaurants. We build a custom `BeforeAgent` middleware to intercept messages *before* the LLM is invoked.

```python
from langchain.agents.middleware import AgentMiddleware, hook_config

class CompetitorFilterMiddleware(AgentMiddleware):
    def __init__(self, competitors):
        super().__init__()
        self.competitors = competitors

    @hook_config(can_jump_to=["end"])
    def before_agent(self, state, runtime):
        # Crucial: Check the LATEST message in the conversation thread
        last_message = state["messages"][-1] 
        
        if last_message.type != "human": return None

        content = last_message.content.lower()
        for competitor in self.competitors:
            if competitor in content:
                # Intercept and reply immediately without calling the LLM
                return {
                    "messages": [{
                        "role": "assistant",
                        "content": "I'm lovin' it, but I can only help with McDonald's! 🍔"
                    }],
                    "jump_to": "end",
                }
        return None

competitor_filter = CompetitorFilterMiddleware(
    ["burger king", "wendys", "kfc", "taco bell"]
)
```
*Pro Tip: Always check `state["messages"][-1]` in multi-turn conversational agents. Checking index `0` will cause the thread to permanently lock up if the user makes a violation in their very first message!*

---

### Step 4: Layer 3 — Manager Approval (Human-in-the-Loop)
Browsing the menu is safe, but actually **placing an order** costs money. We want a fast-food manager to approve orders before the [place_order](file:///Users/shardulmac/Documents/Projects/Projects/LangChain/AdvancedUsecases/Guardrails/guardrails_logic.py#230-261) tool executes.

```python
from langchain.agents.middleware import HumanInTheLoopMiddleware

hitl_middleware = HumanInTheLoopMiddleware(
    interrupt_on={
        "place_order": True,   # Execution halts for approval
        "cancel_order": True,  # Execution halts for approval
        "get_menu": False,     # Safe to run autonomously
    }
)
```
When McBuddy tries to place an order, execution suspends. The UI prompts the human manager, and the agent only resumes once the "Approve" API endpoint is hit.

---

### Step 5: Layer 4 — Brand Sentiment (After-Agent Middleware)
Finally, what if the LLM hallucinates a rude response? We use a fast, cheap LLM-as-a-judge as an [after_agent](file:///Users/shardulmac/Documents/Projects/Projects/LangChain/AdvancedUsecases/Guardrails/guardrails_logic.py#415-453) guardrail. 

Before the message is sent to the user, we evaluate it:

```python
class SentimentGuardrailMiddleware(AgentMiddleware):
    def __init__(self):
        super().__init__()
        self.evaluator = init_chat_model("gemini-2.5-flash")

    @hook_config(can_jump_to=["end"])
    def after_agent(self, state, runtime):
        last_message = state["messages"][-1]
        
        prompt = f'Respond FRIENDLY or UNFRIENDLY for this text: {last_message.content}'
        eval_result = self.evaluator.invoke(prompt).content
        
        if "UNFRIENDLY" in eval_result:
            # Overwrite the rude message with a canned apology
            last_message.content = "I'm sorry! Let me get a crew member to help you. 🍟"
            
        return None
```

---

### Step 6: Stacking the Guardrails
Building the final, production-ready agent is as simple as stacking our middlewares:

```python
from langgraph.checkpoint.memory import InMemorySaver

agent = create_agent(
    model=agent_model,
    tools=[get_menu, place_order, cancel_order],
    system_prompt=SYSTEM_PROMPT,
    middleware=[
        competitor_filter,            # 1. Block bad topics
        pii_email_input,              # 2. Redact PII
        pii_credit_card_input,        # 3. Mask Financials
        hitl_middleware,              # 4. Require human approval for orders
        SentimentGuardrailMiddleware() # 5. Final outbound tone check
    ],
    checkpointer=InMemorySaver(),
)
```

## Conclusion

Building AI features isn't just about prompt engineering; it's about controlling what goes in and what comes out. By establishing deterministic rules (like PII masking and competitor filtering) alongside model-based checks (like sentiment analysis), you can build systems that are not only intelligent but exceptionally safe.

LangChain's Middleware architecture provides an incredibly clean, composable way to achieve this. Now you can let your AI interact with customers, confident that it won't stray off-menu! 🍟✨

---
*Have you implemented guardrails in your GenAI apps? Let me know your best strategies in the comments below!*
