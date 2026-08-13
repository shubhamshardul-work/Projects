import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# Load API key
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

FAISS_INDEX_PATH = r"Project_03\faiss_index"

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Load saved index if it exists, otherwise embed and save
if os.path.exists(FAISS_INDEX_PATH):
    vector_store = FAISS.load_local(FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
    print("Loaded existing FAISS index from disk.")
else:
    documents = PyPDFLoader(r"Project_03\One_Piece.pdf").load()
    print(f"Loaded {len(documents)} pages.")
    chunks = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_documents(documents)
    print(f"Split into {len(chunks)} chunks.")
    vector_store = FAISS.from_documents(chunks, embeddings)
    vector_store.save_local(FAISS_INDEX_PATH)
    print("Embedded and saved FAISS index to disk.")

# Retriever
retriever = vector_store.as_retriever(search_kwargs={"k": 4})

# LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY, temperature=0.2)

# Prompt
prompt = ChatPromptTemplate.from_template("""Use the context to answer the question.
If the answer is not in the context, say "I don't know based on the provided document."

Context: {context}

Question: {question}

Answer:""")

# Chain
chain = (
    {"context": retriever | (lambda docs: "\n\n".join(d.page_content for d in docs)), "question": RunnablePassthrough()}
    | prompt
    | llm
    | StrOutputParser()
)

# Q&A loop
print("\nRAG ready. Type 'exit' to quit.\n")
while True:
    question = input("Your question: ").strip()
    if question.lower() in ("exit", "quit"):
        break
    if question:
        print(f"Answer: {chain.invoke(question)}\n")
        source_docs = retriever.invoke(question)
        print("--- Source Chunks ---")
        for i, doc in enumerate(source_docs, 1):
            print(f"[{i}] Page {doc.metadata.get('page', '?')}: {doc.page_content[:200].strip()}...")
        print()