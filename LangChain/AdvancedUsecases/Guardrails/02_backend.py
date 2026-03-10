from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List
import uvicorn
import traceback

# Import from guardrails_logic
from guardrails_logic import agent, get_content_as_string, logger
from langgraph.types import Command

app = FastAPI(title="Guardrails Chatbot API")

# Enable CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the chatbot UI as static files
app.mount("/ui", StaticFiles(directory="chatbot-ui", html=True), name="chatbot-ui")

@app.get("/")
async def root_redirect():
    """Redirect root to the chatbot UI."""
    return RedirectResponse(url="/ui/")


class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    thread_id: str
    session_token: str

class ApprovalRequest(BaseModel):
    thread_id: str
    decision: str  # "approve" or "reject"


@app.post("/chat")
async def chat(request: ChatRequest):
    config = {
        "configurable": {
            "thread_id": request.thread_id,
            "session_token": request.session_token,
        }
    }

    # Get raw user input for logging
    raw_input = request.messages[-1].content if request.messages else ""
    logger.start_entry(request.thread_id, raw_input)

    try:
        input_messages = [{"role": m.role, "content": m.content} for m in request.messages]

        result = agent.invoke({"messages": input_messages}, config=config)

        last_message = result["messages"][-1]
        content_str = get_content_as_string(last_message.content)

        # Check if the agent is paused for Human-in-the-loop
        is_paused = False
        if "paused for approval" in content_str.lower():
            is_paused = True

        # Gather guardrail metadata and trace data
        guardrails_triggered = []
        trace_data = {}
        if logger._current_entry:
            trace_data = {
                "user_input_raw": logger._current_entry.get("user_input_raw"),
                "llm_input": logger._current_entry.get("llm_input"),
                "llm_raw_output": logger._current_entry.get("llm_raw_output"),
            }
            for g in logger._current_entry.get("guardrails_pipeline", []):
                if g["action"] != "PASS":
                    guardrails_triggered.append({
                        "stage": g["stage"],
                        "action": g["action"],
                        "detail": g.get("detail", "")
                    })

        logger.finish_entry(final_response=content_str)

        return {
            "role": "assistant",
            "content": content_str,
            "is_paused": is_paused,
            "thread_id": request.thread_id,
            "guardrails": guardrails_triggered,
            "trace": trace_data,
        }
    except Exception as e:
        error_str = str(e)
        logger.finish_entry(error=error_str)

        # PII Blocking middleware raises exceptions
        if "PIIMiddleware" in error_str or "block" in error_str.lower():
            return {
                "role": "assistant",
                "content": "🔒 Your message was blocked because it contained content that violates our security policy (e.g., suspicious URLs). Please try rephrasing.",
                "is_blocked": True,
                "guardrails": [{"stage": "PII URL Block", "action": "BLOCK", "detail": "Suspicious URL detected"}],
            }

        # Rate limit errors
        if "RESOURCE_EXHAUSTED" in error_str or "429" in error_str:
            return {
                "role": "assistant",
                "content": "⏳ I'm a bit overwhelmed right now. Please wait a moment and try again.",
                "guardrails": [{"stage": "Rate Limit", "action": "THROTTLED", "detail": "API quota exceeded"}],
            }

        # Generic fallback
        print(f"[ERROR] {traceback.format_exc()}")
        return {
            "role": "assistant",
            "content": "I'm sorry, something went wrong on my end. Please try again in a moment.",
            "guardrails": [],
        }


@app.post("/approve")
async def approve(request: ApprovalRequest):
    config = {"configurable": {"thread_id": request.thread_id}}

    try:
        decision_cmd = Command(resume={"decisions": [{"type": request.decision}]})
        result = agent.invoke(decision_cmd, config=config)

        last_message = result["messages"][-1]

        return {
            "role": "assistant",
            "content": get_content_as_string(last_message.content),
            "thread_id": request.thread_id,
            "guardrails": [],
        }
    except Exception as e:
        print(f"[ERROR] Approval: {e}")
        return {
            "role": "assistant",
            "content": "Error processing the approval. Please try again.",
            "guardrails": [],
        }


@app.get("/logs")
async def get_logs():
    """Return all conversation logs for review."""
    return {"logs": logger.get_all_logs()}


if __name__ == "__main__":
    print("🚀 Backend running at http://localhost:8001")
    print("🌐 Open chatbot at http://localhost:8001/ui/")
    uvicorn.run(app, host="0.0.0.0", port=8001)
