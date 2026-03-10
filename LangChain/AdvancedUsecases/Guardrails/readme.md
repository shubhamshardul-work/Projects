# McBuddy: McDonald's Ordering Assistant with LangChain Guardrails 🍟🤖

McBuddy is a production-grade AI Ordering Assistant for McDonald's, built using **LangChain** and **LangGraph**. It demonstrates a robust, 4-layer guardrail architecture designed to keep conversational agents safe, private, and strictly on-brand.

---

## 🌟 Key Features

- **McD Persona**: A warm, enthusiastic ordering assistant equipped with menu browsing, order placement, and cancellation tools.
- **4-Layer Defense**: Comprehensive security coverage including PII redaction, human-in-the-loop, competitor filters, and sentiment analysis.
- **Premium UI**: A sleek, McDonald's-branded (Red/Gold) web interface with real-time guardrail feedback and a deep-dive trace viewer.
- **Multi-Turn Logic**: Advanced custom middleware that fixes the "permanent thread-lock" common in naive guardrail implementations.

---

## 🛡️ Guardrail Architecture

The agent uses **LangChain AgentMiddleware** to stack safety layers:

| Layer | Type | Guardrail | Action |
|-------|------|-----------|---------|
| **1. Privacy** | PII | `PIIMiddleware` | Redacts emails, masks credit cards, and blocks external URLs in user input. |
| **2. Control** | HITL | `HumanInTheLoopMiddleware` | Interrupts the agent to require manager approval for placing or cancelling orders. |
| **3. Safety** | Before-Agent | `CompetitorFilterMiddleware` | Intercepts and blocks mentions of rival food chains (Burger King, KFC, etc.) *before* the LLM is called. |
| **4. Persona** | After-Agent | `SentimentGuardrailMiddleware` | Evaluates LLM responses to ensure they are polite and professional; rewrites anything "unfriendly". |

---

## 🛠️ Tech Stack

- **LLM**: Google Gemini 1.5 Flash (via `langchain-google-genai`).
- **Orchestration**: LangGraph (Stateful, multi-turn conversation management).
- **Backend**: FastAPI (Python).
- **Frontend**: Vanilla HTML/JS with a glassmorphic McD-inspired design system.

---

## 🚀 Getting Started

### 1. Setup Environment
Ensure you have your `.env` file configured with your Gemini API key:
```env
GOOGLE_API_KEY=your_key_here
```

### 2. Start the Backend
```bash
python 02_backend.py
```
Wait for the terminal to show `🚀 Backend running at http://localhost:8001`.

### 3. Open the UI
Open your browser and navigate to:
[http://localhost:8001/ui/](http://localhost:8001/ui/)

---

## 🧪 Test Scenarios

1.  **Safety**: Type *"How does your burger compare to Burger King?"* — McBuddy will politely refuse to discuss competitors.
2.  **Privacy**: Type *"I want to order a Big Mac, my email is test@example.com"* — View the **Trace Viewer** to see how the email was redacted before reaching the LLM.
3.  **Governance**: Ask to place an order — A manager approval modal will pop up, demonstrating Human-in-the-Loop.
4.  **Resilience**: Mention a competitor, get blocked, and then ask for the menu in the **same turn**. McBuddy will recover instantly and show you the menu.

---

## 📝 Project Structure

- `guardrails_logic.py`: The "brains" — contains the agent definition, tools, and all custom middleware logic.
- `02_backend.py`: The FastAPI server bridging the agent to the web.
- `chatbot-ui/`: The premium frontend interface.
- `guardrails_logs/`: Continuous JSON logging of every guardrail action and LLM trace.
