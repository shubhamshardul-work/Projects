import os
import argparse
from datetime import datetime
from dotenv import load_dotenv
from src.graph import build_graph

def main():
    load_dotenv()
    
    # Suppress deep internal Pydantic serialization warnings from LangChain-Google
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")
    
    parser = argparse.ArgumentParser(description="GenAI News Fetcher")
    parser.add_argument("--query", type=str, default="latest breakthroughs, releases, and news in Generative AI", help="Search query")
    parser.add_argument("--output", type=str, default="reports/genai_news_{date}.md", help="Output markdown file path")
    parser.add_argument("--days", type=int, default=2, help="Number of days to look back for recent news. Default 2.")
    
    args = parser.parse_args()
    
    if not os.getenv("GOOGLE_API_KEY") or not os.getenv("TAVILY_API_KEY"):
        print("Warning: GOOGLE_API_KEY and TAVILY_API_KEY must be set in the environment.")
        
    # Format output path with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_path = f"reports/genai_news_{timestamp}.md"
    state_path = f"state/genai_news_{timestamp}.json"
    
    # Ensure directories exist
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
        
    graph = build_graph()
    
    print(f"Starting fetch for query: '{args.query}'...")
    
    try:
        final_state = graph.invoke({"search_query": args.query, "days": args.days})
        report = final_state.get("final_report", "Generation failed. No report produced.")
        
        # Save markdown report
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
            
        # Save JSON state
        import json
        with open(state_path, "w", encoding="utf-8") as f:
            # Handle potential non-serializable objects in raw_news by using a custom encoder or stringification
            json.dump(final_state, f, indent=2, default=str)
            
        print(f"Success! Report saved to {report_path}")
        print(f"Success! State saved to {state_path}")
    except Exception as e:
        print(f"An error occurred during execution: {e}")

if __name__ == "__main__":
    main()
