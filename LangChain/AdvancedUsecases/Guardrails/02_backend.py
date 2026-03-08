from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn

# Import the agent and necessary components from guardrails_logic
from guardrails_logic import agent
from langgraph.types import Command

app = FastAPI(title="Guardrails Chatbot API")

# Enable CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    thread_id: str
    session_token: str

class ApprovalRequest(BaseModel):
    thread_id: str
    decision: str # "approve" or "reject"

@app.post("/chat")
async def chat(request: ChatRequest):
    config = {
        "configurable": {
            "thread_id": request.thread_id,
            "session_token": request.session_token,
        }
    }
    
    try:
        # Convert Pydantic messages to dicts for LangChain
        input_messages = [{"role": m.role, "content": m.content} for m in request.messages]
        
        result = agent.invoke({"messages": input_messages}, config=config)
        
        last_message = result["messages"][-1]
        
        # Check if the agent is paused for Human-in-the-loop
        # This is a simplified check for demo purposes
        is_paused = False
        # In a real LangGraph setup, we'd check the thread state. 
        # For this demo, we'll look for specific markers or state patterns.
        if "paused for approval" in last_message.content.lower():
            is_paused = True

        return {
            "role": "assistant",
            "content": last_message.content,
            "is_paused": is_paused,
            "thread_id": request.thread_id
        }
    except Exception as e:
        # PII Blocking middleware might raise an exception
        if "PIIMiddleware" in str(e) or "block" in str(e).lower():
            return {
                "role": "assistant",
                "content": f"Security Alert: Your message was blocked due to a policy violation. (Reason: {str(e)})",
                "is_blocked": True
            }
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/approve")
async def approve(request: ApprovalRequest):
    config = {"configurable": {"thread_id": request.thread_id}}
    
    try:
        decision_cmd = Command(resume={"decisions": [{"type": request.decision}]})
        result = agent.invoke(decision_cmd, config=config)
        
        last_message = result["messages"][-1]
        
        return {
            "role": "assistant",
            "content": last_message.content,
            "thread_id": request.thread_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
