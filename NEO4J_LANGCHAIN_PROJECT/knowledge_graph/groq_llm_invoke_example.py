from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

import os

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.environ.get("GROQ_API_KEY", ""),
    temperature=0.7
)

# Using messages
messages = [
    HumanMessage(content="Explain quantum computing in simple terms")
]

response = llm.invoke(messages)
print(response.content)