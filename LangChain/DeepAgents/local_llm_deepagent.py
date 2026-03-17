import os
import json
from typing import Any, Literal
from pydantic import BaseModel, Field
from tavily import TavilyClient
from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage
from langchain.agents.middleware.types import AgentMiddleware
from deepagents import create_deep_agent

# ==============================================================================
# PREREQUISITES:
# 1. Install dependencies: pip install -r requirements.txt
# 2. Ensure Ollama is running and qwen2.5-coder:7b is pulled.
# 3. Ensure TAVILY_API_KEY is set in your environment or .env file.
# ==============================================================================

# Load .env if it exists
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))

class WeatherReport(BaseModel):
    """A structured weather report with current conditions and forecast."""
    location: str = Field(description="The location for this weather report")
    temperature: float = Field(description="Current temperature in Celsius")
    condition: str = Field(description="Current weather condition (e.g., sunny, cloudy, rainy)")
    humidity: int = Field(description="Humidity percentage")
    wind_speed: float = Field(description="Wind speed in km/h")
    forecast: str = Field(description="Brief forecast for the next 24 hours")

def internet_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news", "finance"] = "general",
    include_raw_content: bool = False,
):
    """Run a web search using Tavily."""
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise ValueError("TAVILY_API_KEY not found in environment variables.")
    
    tavily_client = TavilyClient(api_key=api_key)
    return tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )

class SmoothToolCalls(AgentMiddleware):
    """
    Middleware to intercept local model outputs that contain raw JSON tool calls
    in the message content and convert them into proper ToolCalls for the agent.
    """
    def wrap_model_call(self, request: Any, handler: Any) -> Any:
        response = handler(request)
        
        # If the model didn't provide tool_calls but content looks like a tool call JSON
        if hasattr(response, "tool_calls") and not response.tool_calls and response.content:
            content = response.content.strip()
            
            # Handle possible markdown blocks
            if "```json" in content:
                content = content.split("```json")[-1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[-1].split("```")[0].strip()
            
            if content.startswith("{") and "name" in content:
                try:
                    data = json.loads(content)
                    if isinstance(data, dict) and "name" in data and ("arguments" in data or "args" in data):
                        name = data["name"]
                        args = data.get("arguments") or data.get("args")
                        
                        # Add the tool call to the response object or create a new one
                        # In LangChain, response is usually a message object like AIMessage
                        response.tool_calls = [{
                            "name": name,
                            "args": args,
                            "id": f"call_{os.urandom(4).hex()}"
                        }]
                        print(f"--- [Middleware]: Smoothed raw JSON into tool call: {name} ---")
                except:
                    pass
        return response

def main():
    print("Initializing Structured Deep Agent with local qwen2.5-coder:7b...")
    
    # 1. Initialize the local Ollama model
    model = ChatOllama(
        model="qwen2.5-coder:7b",
        temperature=0,
    )
    
    # 2. Create the deep agent with structured output, search tools, and smoothing middleware
    agent = create_deep_agent(
        model=model,
        response_format=WeatherReport,
        tools=[internet_search],
        middleware=[SmoothToolCalls()],
        system_prompt=(
            "You are a weather assistant. Your task is to provide a structured weather report.\n\n"
            "CRITICAL: To find the weather, you MUST use the `internet_search` tool. "
            "Do not provide a report based on internal knowledge.\n\n"
            "When you have the search results, use the provided schema to return the final answer.\n"
            "To use a tool, respond with a JSON object like: "
            '{"name": "tool_name", "arguments": {"arg1": "val1"}}'
        )
    )
    
    # 3. Invoke the agent with streaming to see internal steps
    address = "San Francisco"
    print(f"\n[Task]: Getting weather report for {address}...\n")
    print("--- Agent is thinking ---\n")
    
    # Check for TAVILY_API_KEY
    if not os.environ.get("TAVILY_API_KEY"):
        for path in [".env", "../.env", "../../.env"]:
            if os.path.exists(path):
                load_dotenv(path)
                if os.environ.get("TAVILY_API_KEY"):
                    break
    
    config = {"configurable": {"thread_id": "weather_test"}}
    inputs = {"messages": [{"role": "user", "content": f"Find the current weather in {address} and give me a detailed report."}]}
    
    last_response = None
    try:
        for chunk in agent.stream(inputs, config, stream_mode="values", recursion_limit=20):
            if "messages" in chunk:
                msg = chunk["messages"][-1]
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        print(f"--- [Logical Tool Call]: {tc['name']} ---")
            last_response = chunk
    except Exception as e:
        print(f"\n[Error during execution]: {e}")

    # 4. Output the result
    print("\n--- Final Structured Response ---\n")
    if last_response and "structured_response" in last_response:
        report = last_response["structured_response"]
        print(f"Location: {report.location}")
        print(f"Temperature: {report.temperature}°C")
        print(f"Condition: {report.condition}")
        print(f"Humidity: {report.humidity}%")
        print(f"Wind Speed: {report.wind_speed} km/h")
        print(f"Forecast: {report.forecast}")
    else:
        print("Error: No structured response received.")
        if last_response and last_response.get('messages'):
             print(f"Last message content: {last_response['messages'][-1].content}")

if __name__ == "__main__":
    main()
