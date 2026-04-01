import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from dotenv import load_dotenv

load_dotenv()

# Initialize the Gemini LLM
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.7,
)

# Define messages
messages = [
    SystemMessage(content="You are a helpful assistant."),
    HumanMessage(content="What is a knowledge graph? Explain in 3 sentences."),
]

# Invoke the LLM
response = llm.invoke(messages)

print("Response:", response.content)