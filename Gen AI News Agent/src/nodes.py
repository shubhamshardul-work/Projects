import json
from langchain_community.tools.tavily_search import TavilySearchResults
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.state import AgentState

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

def tavily_node(state: AgentState):
    """Fetches news via Tavily."""
    days = state.get("days", 2)
    query = state.get("search_query", "latest breakthroughs and news in Generative AI")
    # Append recency constraint to query
    query = f"{query} published in the last {days} days"
    tavily_tool = TavilySearchResults(max_results=3, search_depth="basic")
    try:
        results = tavily_tool.invoke({"query": query})
        
        # Standardize the output format
        formatted_results = []
        for r in results:
            formatted_results.append({
                "title": f"[Tavily] {r.get('title', 'No Title')}",
                "url": r.get('url', ''),
                "summary": r.get('content', ''),
                "source": "Tavily Search"
            })
    except Exception as e:
        print(f"Error fetching Tavily news: {e}")
        formatted_results = []
    
    return {"tavily_news": formatted_results}

def rss_node(state: AgentState):
    """Fetches news from hardcoded RSS feeds."""
    import email.utils
    from datetime import timezone
    days = state.get("days", 2)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    feeds = [
        "https://openai.com/blog/rss.xml",
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        "https://venturebeat.com/category/ai/feed/"
    ]
    
    results = []
    for url in feeds:
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                items = list(root.findall('./channel/item'))
                for item in items[:10]:
                    # Check publication date
                    pub_date_el = item.find('pubDate')
                    if pub_date_el is not None and pub_date_el.text:
                        try:
                            # Use email.utils to parse standard RSS date format
                            import email.utils
                            pub_dt = email.utils.parsedate_to_datetime(pub_date_el.text)
                            if pub_dt and pub_dt < cutoff:
                                continue  # Skip old news
                        except Exception:
                            pass # Fallback to keeping it if parsing fails
                            
                    title = item.find('title').text if item.find('title') is not None else "No Title"
                    link = item.find('link').text if item.find('link') is not None else ""
                    description = item.find('description').text if item.find('description') is not None else ""
                    
                    # Clean up HTML tags from description if any
                    import re
                    clean_description = re.sub(r'<[^>]+>', '', description)[:300] if description else ""
                    
                    results.append({
                        "title": f"[RSS] {title}", 
                        "url": link, 
                        "summary": clean_description,
                        "source": url
                    })
        except Exception as e:
            print(f"Error fetching RSS {url}: {e}")
            
    # Keep only the top 5 most recent across all feeds to prevent bloat
    return {"rss_news": results[:5]}

def arxiv_node(state: AgentState):
    """Fetches latest AI papers from ArXiv API."""
    from datetime import timezone
    days = state.get("days", 2)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    try:
        url = "http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.LG&sortBy=lastUpdatedDate&sortOrder=desc&max_results=10"
        response = requests.get(url, timeout=5)
        results = []
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            # ArXiv uses Atom namespace
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            for entry in root.findall('atom:entry', ns):
                # Filter by update date
                updated_el = entry.find('atom:updated', ns)
                if updated_el is not None and updated_el.text:
                    try:
                        updated_dt = datetime.fromisoformat(updated_el.text.replace("Z", "+00:00"))
                        if updated_dt < cutoff:
                            continue # Skip old papers
                    except Exception:
                        pass
                        
                title_el = entry.find('atom:title', ns)
                title = title_el.text.replace('\n', ' ').strip() if title_el is not None and title_el.text else "No Title"
                
                link_el = entry.find('atom:id', ns)
                link = link_el.text if link_el is not None and link_el.text else ""
                
                summary_el = entry.find('atom:summary', ns)
                summary_text = summary_el.text if summary_el is not None and summary_el.text else ""
                summary = summary_text[:200] + "..." if summary_text else ""
                
                results.append({
                    "title": f"[ArXiv] {title}", 
                    "url": link, 
                    "summary": summary,
                    "source": "ArXiv API"
                })
    except Exception as e:
        print(f"Error fetching ArXiv: {e}")
        results = []
        
    return {"arxiv_news": results}

def github_node(state: AgentState):
    """Fetches trending AI repositories from GitHub."""
    days = state.get("days", 2)
    try:
        # Search for repos created in the last X days with AI topics
        date_str = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        url = f"https://api.github.com/search/repositories?q=topic:llm+OR+topic:generative-ai+created:>{date_str}&sort=stars&order=desc&per_page=3"
        response = requests.get(url, timeout=5)
        results = []
        if response.status_code == 200:
            data = response.json()
            for repo in data.get("items", []):
                results.append({
                    "title": f"[GitHub] {repo['full_name']} (⭐ {repo['stargazers_count']})",
                    "url": repo['html_url'],
                    "summary": repo.get('description', '') or 'No description',
                    "source": "GitHub Trending"
                })
    except Exception as e:
        print(f"Error fetching GitHub: {e}")
        results = []
        
    return {"github_news": results}

def hf_node(state: AgentState):
    """Fetches trending models from Hugging Face."""
    try:
        url = "https://huggingface.co/api/models?sort=trendingScore&direction=-1&limit=3"
        response = requests.get(url, timeout=5)
        results = []
        if response.status_code == 200:
            data = response.json()
            for model in data:
                results.append({
                    "title": f"[HuggingFace] {model.get('id', 'Unknown Model')}",
                    "url": f"https://huggingface.co/{model.get('id')}",
                    "summary": f"Trending HF Model. Downloads: {model.get('downloads', 0)}",
                    "source": "Hugging Face API"
                })
    except Exception as e:
        print(f"Error fetching Hugging Face: {e}")
        results = []
        
    return {"hf_news": results}

def aggregate_node(state: AgentState):
    """Aggregates all fetched news into a single list."""
    combined = []
    combined.extend(state.get("tavily_news", []))
    combined.extend(state.get("rss_news", []))
    combined.extend(state.get("arxiv_news", []))
    combined.extend(state.get("github_news", []))
    combined.extend(state.get("hf_news", []))
    
    return {"raw_news": combined}

def curate_node(state: AgentState):
    """Filters and curates the most important news."""
    days = state.get("days", 2)
    raw_news = state.get("raw_news", [])
    if not raw_news:
        return {"curated_news": []}
    
    # We will use an LLM to select the top impactful news
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0,
        convert_system_message_to_human=True
    )
    
    from datetime import datetime
    today_str = datetime.now().strftime('%Y-%m-%d')
    prompt = f"""
    You are an expert AI news curator evaluating articles on {today_str}.
    Given the following list of raw news articles fetched from various sources,
    select the most important and impactful news stories in the field of Generative AI published in the last {days} days.
    
    IMPORTANT INSTRUCTIONS: 
    1. Filter out noise, clickbait, or less relevant articles. Focus on major releases, strategic partnerships, and frontier model updates.
    2. CRITICAL: Search engines sometimes return highly-ranked but OUTDATED news (e.g., Google rebranding Bard to Gemini in early 2024, or old OpenAI releases). 
       You MUST actively filter out any news that is older than {days} days. If an article describes an event that clearly happened months or years ago relative to {today_str}, DISCARD IT.
    3. If an article has a short or missing summary, judge its relevance and age based on its title and URL.
    
    News Articles:
    {raw_news}
    
    Return ONLY a valid JSON list of objects containing 'title', 'url', and a short 'summary'.
    Do not include any other text, markdown formatting, or explanations before or after the JSON.
    """
    
    response = llm.invoke([
        SystemMessage(content="You return ONLY valid JSON and absolutely nothing else."), 
        HumanMessage(content=prompt)
    ])
    
    # Debugging output for development
    print(f"Curator LLM response length: {len(response.content)}")
    
    try:
        content = response.content.strip()
        # Find the first '[' and last ']' to extract just the JSON array, ignoring any conversational text
        start_idx = content.find('[')
        end_idx = content.rfind(']')
        
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            json_str = content[start_idx:end_idx+1]
            curated = json.loads(json_str)
        else:
            raise ValueError(f"Could not find JSON array in response.")
            
    except Exception as e:
        print(f"Error parsing curated news: {e}\nResponse was: {response.content}")
        curated = []
        
    return {"curated_news": curated}

def summarize_node(state: AgentState):
    """Generates the final markdown report."""
    curated_news = state.get("curated_news", [])
    if not curated_news:
        return {"final_report": "No significant news found today."}
        
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.2,
        convert_system_message_to_human=True
    )
    
    prompt = f"""
    You are an expert tech journalist. Write a concise, highly engaging markdown report 
    summarizing the following top Generative AI news.
    
    Instructions:
    - Start with an engaging title and a very short introduction (1-2 sentences).
    - For each news item, provide a bolded catchy headline linked to the source URL.
    - Write a short, insightful paragraph for each news item explaining why it matters.
    - Keep it professional, objective, yet interesting.
    - Conclude with a brief closing thought on the trend.
    
    Curated News:
    {json.dumps(curated_news, indent=2)}
    """
    
    response = llm.invoke([
        SystemMessage(content="You are a helpful assistant writing markdown reports."), 
        HumanMessage(content=prompt)
    ])
    
    return {"final_report": response.content}
